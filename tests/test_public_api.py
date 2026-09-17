from woobe import Woobe


def test_chat_is_lazy_and_has_no_runtime_identity_before_iteration() -> None:
    woobe = Woobe(base_url="http://localhost:9999")
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    chat = agent.chat(input="Olá")

    assert chat.session_id is None
    assert chat.run_id is None
    assert chat.target_alias == "support"
