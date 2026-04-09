from __future__ import annotations

import asyncio
import json
import os
import socket
import struct
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Awaitable, Callable

DEFAULT_STARTUP_TIMEOUT_SEC = 5.0
_INTERNAL_AUTH_FIELD = '__internalCommandAuthToken'
_INTERNAL_REGISTER_TYPE = '__register_internal_client__'
_INTERNAL_EPOCH_FIELD = '__internalCommandLeaseEpoch'


class InternalCommandSocketServer:
    """Background UNIX socket reserved for API-facade command ingress.

    The server only accepts commands from one registered client process at a
    time. A runtime secret must be presented during registration and on every
    command. Successful registration allocates a monotonically increasing lease
    epoch; commands must present that epoch and originate from the same peer
    PID/UID/GID tuple for the lifetime of the lease.
    """

    def __init__(
        self,
        *,
        socket_path: str,
        auth_token: str,
        request_handler: Callable[[dict[str, Any]], Awaitable[None]] | Callable[[dict[str, Any]], None],
        stats_callback: Callable[[str], None] | Callable[..., None] | None = None,
    ) -> None:
        self.socket_path = str(socket_path).strip()
        self.auth_token = str(auth_token or '').strip()
        self.request_handler = request_handler
        self.stats_callback = stats_callback
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.server: asyncio.base_events.Server | None = None
        self._startup_future: Future[dict[str, Any]] | None = None
        self._thread_lock = threading.Lock()
        self._authorized_pid: int | None = None
        self._authorized_uid: int | None = None
        self._authorized_gid: int | None = None
        self._lease_epoch: int = 0

    def _report(self, kind: str, **payload: Any) -> None:
        if self.stats_callback is None:
            return
        try:
            self.stats_callback(kind, **payload)
        except TypeError:
            try:
                self.stats_callback(kind)
            except Exception:
                return
        except Exception:
            return

    async def _dispatch(self, payload: dict[str, Any]) -> None:
        result = self.request_handler(payload)
        if asyncio.iscoroutine(result):
            await result

    def _peer_credentials(self, writer: asyncio.StreamWriter) -> dict[str, int | None]:
        sock = writer.get_extra_info('socket')
        if sock is None or not hasattr(socket, 'SO_PEERCRED'):
            return {'pid': None, 'uid': None, 'gid': None}
        try:
            raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
            pid, uid, gid = struct.unpack('3i', raw)
            return {'pid': int(pid), 'uid': int(uid), 'gid': int(gid)}
        except Exception:
            return {'pid': None, 'uid': None, 'gid': None}

    def _register_peer(self, peer: dict[str, int | None]) -> int:
        self._authorized_pid = int(peer['pid']) if peer.get('pid') is not None else None
        self._authorized_uid = int(peer['uid']) if peer.get('uid') is not None else None
        self._authorized_gid = int(peer['gid']) if peer.get('gid') is not None else None
        self._lease_epoch += 1
        return self._lease_epoch

    def _peer_is_authorized(self, peer: dict[str, int | None]) -> bool:
        return (
            self._authorized_pid is not None
            and peer.get('pid') == self._authorized_pid
            and peer.get('uid') == self._authorized_uid
            and peer.get('gid') == self._authorized_gid
        )

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = self._peer_credentials(writer)
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if not raw:
                response = {'ok': False, 'message': 'empty payload'}
            elif not self.auth_token:
                response = {'ok': False, 'message': 'internal command socket auth token is not configured'}
            else:
                try:
                    payload = json.loads(raw.decode('utf-8'))
                except Exception as exc:
                    response = {'ok': False, 'message': f'invalid json payload: {exc}'}
                else:
                    if not isinstance(payload, dict):
                        response = {'ok': False, 'message': 'json payload must be an object'}
                    else:
                        provided_token = str(payload.get(_INTERNAL_AUTH_FIELD, '') or '')
                        if not provided_token or provided_token != self.auth_token:
                            response = {'ok': False, 'message': 'internal command socket authentication failed'}
                        elif str(payload.get('type', '') or '') == _INTERNAL_REGISTER_TYPE:
                            lease_epoch = self._register_peer(peer)
                            response = {'ok': True, 'registered': True, 'peerPid': self._authorized_pid, 'leaseEpoch': lease_epoch}
                            self._report('internal_command_socket_registered', socketPath=self.socket_path, peerPid=self._authorized_pid, leaseEpoch=lease_epoch)
                        elif not self._peer_is_authorized(peer):
                            response = {'ok': False, 'message': 'internal command socket peer is not authorized'}
                        elif int(payload.get(_INTERNAL_EPOCH_FIELD, -1) or -1) != self._lease_epoch:
                            response = {'ok': False, 'message': 'internal command socket lease epoch mismatch', 'expectedLeaseEpoch': self._lease_epoch}
                        else:
                            sanitized = dict(payload)
                            sanitized.pop(_INTERNAL_AUTH_FIELD, None)
                            sanitized.pop(_INTERNAL_EPOCH_FIELD, None)
                            await self._dispatch(sanitized)
                            response = {'ok': True, 'leaseEpoch': self._lease_epoch}
            writer.write((json.dumps(response, ensure_ascii=False) + '\n').encode('utf-8'))
            await writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                writer.write((json.dumps({'ok': False, 'message': str(exc)}, ensure_ascii=False) + '\n').encode('utf-8'))
                await writer.drain()
            except Exception:
                pass
            self._report('internal_command_socket_error', error=str(exc))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def _cleanup_socket_file(self) -> None:
        path = Path(self.socket_path)
        try:
            if path.exists() or path.is_symlink():
                path.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            return

    async def _async_start(self) -> dict[str, Any]:
        path = Path(self.socket_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        self._cleanup_socket_file()
        self.server = await asyncio.start_unix_server(self._handle, path=self.socket_path)
        os.chmod(self.socket_path, 0o600)
        metadata = {'socketPath': self.socket_path}
        self._report('internal_command_socket_listening', **metadata)
        return metadata

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        try:
            startup = loop.run_until_complete(self._async_start())
            assert self._startup_future is not None
            self._startup_future.set_result(startup)
            loop.run_forever()
        except Exception as exc:
            if self._startup_future is not None and not self._startup_future.done():
                self._startup_future.set_exception(exc)
            self._report('internal_command_socket_failed', error=str(exc), socketPath=self.socket_path)
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            if self.server is not None:
                self.server.close()
                loop.run_until_complete(self.server.wait_closed())
                self.server = None
            self._cleanup_socket_file()
            loop.close()
            self.loop = None

    def start(self, *, timeout_sec: float = DEFAULT_STARTUP_TIMEOUT_SEC) -> dict[str, Any]:
        with self._thread_lock:
            if self.thread is not None and self.thread.is_alive():
                return {'socketPath': self.socket_path}
            self._startup_future = Future()
            self.thread = threading.Thread(target=self._thread_main, daemon=True)
            self.thread.start()
        try:
            return self._startup_future.result(timeout=max(0.1, float(timeout_sec)))
        except Exception as exc:
            self.stop()
            raise RuntimeError(f'internal command socket failed to start: {exc}') from exc

    def stop(self) -> None:
        loop = self.loop
        if loop is None:
            self._cleanup_socket_file()
            return

        async def _shutdown() -> None:
            if self.server is not None:
                self.server.close()
                await self.server.wait_closed()
                self.server = None
            self._cleanup_socket_file()
            self._report('internal_command_socket_stopped', socketPath=self.socket_path)

        future = asyncio.run_coroutine_threadsafe(_shutdown(), loop)
        try:
            future.result(timeout=5.0)
        except Exception:
            pass
        finally:
            loop.call_soon_threadsafe(loop.stop)
            if self.thread is not None:
                self.thread.join(timeout=5.0)
            self.thread = None
            self.loop = None
