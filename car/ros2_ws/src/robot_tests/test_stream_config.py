from robot_vision.stream_config import resolve_stream_url


def test_resolve_stream_url_prefers_stream_and_falls_back_to_mjpeg():
    assert resolve_stream_url(stream_url='http://a/stream', mjpeg_url='http://b/stream') == 'http://a/stream'
    assert resolve_stream_url(stream_url='', mjpeg_url='http://b/stream') == 'http://b/stream'
    assert resolve_stream_url(stream_url='', mjpeg_url='') == ''
