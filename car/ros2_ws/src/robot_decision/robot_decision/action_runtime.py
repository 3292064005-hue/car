from __future__ import annotations

import threading
from typing import Any

import rclpy

if not hasattr(rclpy, 'ok'):  # pragma: no cover - test stubs may omit runtime helpers
    rclpy.ok = lambda: True

from robot_utils.constants import MODE_IDLE, MODE_PATROL, MODE_TRACK


class ActionRuntime:
    """Event-driven bridge between ROS actions and decision task state."""

    def __init__(self, node: Any) -> None:
        self._node = node
        self._condition = threading.Condition()
        self._shutdown_requested = False

    def _patrol_total_points(self) -> int:
        """Return the navigation-authoritative patrol point count.

        Returns:
            Total patrol points reported by the navigation runtime.

        Raises:
            None.

        Boundary behavior:
            The patrol action no longer falls back to ``PatrolManager`` for
            runtime progress or completion semantics. Until navigation reports a
            route, the total remains ``0``.
        """
        return max(0, int(self._node.context.navigation_total_goals or 0))

    def notify_state_change(self) -> None:
        """Wake pending action executors after any relevant state mutation.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        with self._condition:
            self._condition.notify_all()

    def notify_shutdown(self) -> None:
        """Wake pending action executors during node teardown.

        Args:
            None.

        Returns:
            None.

        Raises:
            None.
        """
        with self._condition:
            self._shutdown_requested = True
            self._condition.notify_all()

    def _wait_for_change(self, predicate) -> None:
        """Block until the action state changes or shutdown is requested.

        Args:
            predicate: Callable returning True when the caller should resume.

        Returns:
            None.

        Raises:
            None.
        """
        with self._condition:
            self._condition.wait_for(lambda: self._shutdown_requested or predicate())

    def execute_start_patrol(self, goal_handle: object):
        action_type = self._node._actions['StartPatrol']
        goal = goal_handle.request
        trace_id = str(getattr(goal, 'trace_id', '') or '')
        ok, message = self._node.request_mode_change(MODE_PATROL, getattr(goal, 'requested_by', 'action'), getattr(goal, 'reason', 'start_patrol_action'))
        result = action_type.Result()
        if hasattr(result, 'trace_id'):
            result.trace_id = trace_id
        if not ok:
            result.success = False
            result.message = message
            result.final_mode = self._node.current_mode
            result.completed_points = int(self._node.context.navigation_completed_goals or self._node.context.patrol_index)
            result.progress = float(self._node.context.active_action_progress)
            goal_handle.abort()
            return result
        with self._node._action_lock:
            self._node._active_patrol_goal = goal_handle
        while rclpy.ok() and not self._shutdown_requested:
            if goal_handle.is_cancel_requested:
                self._node.request_mode_change(MODE_IDLE, 'action', 'start_patrol_cancelled')
                result.success = False
                result.message = 'start_patrol cancelled'
                result.final_mode = self._node.current_mode
                result.completed_points = int(self._node.context.navigation_completed_goals or self._node.context.patrol_index)
                result.progress = float(self._node.context.active_action_progress)
                goal_handle.canceled()
                with self._node._action_lock:
                    self._node._active_patrol_goal = None
                with self._node.state_guard():
                    self._node.context.active_action_phase = 'cancelled'
                self.notify_state_change()
                return result
            feedback = action_type.Feedback()
            feedback.phase = self._node.context.active_action_phase or 'running'
            feedback.step_name = self._node.context.current_step_name
            feedback.step_index = int(self._node.context.navigation_completed_goals or self._node.context.patrol_index)
            feedback.completed_points = int(self._node.context.navigation_completed_goals or self._node.context.patrol_index)
            feedback.total_points = self._patrol_total_points()
            feedback.progress = float(self._node.context.active_action_progress)
            feedback.message = self._node.context.active_action_message
            if hasattr(feedback, 'trace_id'):
                feedback.trace_id = trace_id
            goal_handle.publish_feedback(feedback)
            if self._node.context.patrol_completed:
                result.success = True
                result.message = 'patrol completed'
                result.final_mode = self._node.current_mode
                result.completed_points = self._patrol_total_points()
                result.progress = 1.0
                goal_handle.succeed()
                with self._node._action_lock:
                    self._node._active_patrol_goal = None
                return result
            if self._node.current_mode not in {MODE_PATROL, MODE_TRACK} and not self._node.context.patrol_completed:
                result.success = False
                result.message = f'patrol exited in mode {self._node.current_mode}'
                result.final_mode = self._node.current_mode
                result.completed_points = int(self._node.context.navigation_completed_goals or self._node.context.patrol_index)
                result.progress = float(self._node.context.active_action_progress)
                goal_handle.abort()
                with self._node._action_lock:
                    self._node._active_patrol_goal = None
                with self._node.state_guard():
                    self._node.context.active_action_phase = 'aborted'
                self.notify_state_change()
                return result
            self._wait_for_change(lambda: goal_handle.is_cancel_requested or self._node.context.patrol_completed or self._node.current_mode not in {MODE_PATROL, MODE_TRACK})
        result.success = False
        result.message = 'ROS shutdown'
        result.final_mode = self._node.current_mode
        result.completed_points = int(self._node.context.navigation_completed_goals or self._node.context.patrol_index)
        result.progress = float(self._node.context.active_action_progress)
        goal_handle.abort()
        return result

    def execute_track_target(self, goal_handle: object):
        action_type = self._node._actions['TrackTarget']
        goal = goal_handle.request
        trace_id = str(getattr(goal, 'trace_id', '') or '')
        min_confidence = float(getattr(goal, 'min_confidence', 0.0) or 0.0)
        if min_confidence > 0.0:
            self._node.track_manager.min_confidence = min_confidence
        ok, message = self._node.request_mode_change(MODE_TRACK, getattr(goal, 'requested_by', 'action'), getattr(goal, 'reason', 'track_target_action'))
        result = action_type.Result()
        if hasattr(result, 'trace_id'):
            result.trace_id = trace_id
        if not ok:
            result.success = False
            result.message = message
            result.final_mode = self._node.current_mode
            result.lost_target_count = int(self._node.context.lost_target_count)
            goal_handle.abort()
            return result
        with self._node._action_lock:
            self._node._active_track_goal = goal_handle
        while rclpy.ok() and not self._shutdown_requested:
            if goal_handle.is_cancel_requested:
                self._node.request_mode_change(MODE_IDLE, 'action', 'track_target_cancelled')
                result.success = False
                result.message = 'track_target cancelled'
                result.final_mode = self._node.current_mode
                result.lost_target_count = int(self._node.context.lost_target_count)
                goal_handle.canceled()
                with self._node._action_lock:
                    self._node._active_track_goal = None
                with self._node.state_guard():
                    self._node.context.active_action_phase = 'cancelled'
                self.notify_state_change()
                return result
            feedback = action_type.Feedback()
            feedback.target_detected = bool(self._node.last_target and self._node.last_target.detected)
            feedback.target_type = str(getattr(self._node.last_target, 'target_type', '') or self._node.context.last_target_type)
            feedback.confidence = float(getattr(self._node.last_target, 'confidence', 0.0) or 0.0)
            feedback.offset_x = float(getattr(self._node.last_target, 'offset_x', 0.0) or 0.0)
            feedback.offset_y = float(getattr(self._node.last_target, 'offset_y', 0.0) or 0.0)
            feedback.lost_target_count = int(self._node.context.lost_target_count)
            feedback.message = self._node.context.active_action_message or 'tracking'
            if hasattr(feedback, 'trace_id'):
                feedback.trace_id = trace_id
            goal_handle.publish_feedback(feedback)
            if self._node.current_mode != MODE_TRACK:
                result.success = self._node.current_mode == MODE_IDLE
                result.message = 'track_target exited'
                result.final_mode = self._node.current_mode
                result.lost_target_count = int(self._node.context.lost_target_count)
                if result.success:
                    goal_handle.succeed()
                else:
                    goal_handle.abort()
                with self._node._action_lock:
                    self._node._active_track_goal = None
                return result
            self._wait_for_change(lambda: goal_handle.is_cancel_requested or self._node.current_mode != MODE_TRACK)
        result.success = False
        result.message = 'ROS shutdown'
        result.final_mode = self._node.current_mode
        result.lost_target_count = int(self._node.context.lost_target_count)
        goal_handle.abort()
        return result
