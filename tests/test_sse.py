from woobe._transport.sse import SseDecoder


def test_sse_decoder_parses_woobe_frame() -> None:
    decoder = SseDecoder()

    assert decoder.feed_line("id: 7") is None
    assert decoder.feed_line("event: token") is None
    assert decoder.feed_line('data: {"type":"token","content":"Olá"}') is None

    frame = decoder.feed_line("")

    assert frame is not None
    assert frame.event == "token"
    assert frame.event_id == "7"
    assert frame.data["content"] == "Olá"
