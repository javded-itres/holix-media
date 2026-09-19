from holix_media.agent import MediaAgentExtension, get_agent_extension


def test_agent_registers_tools() -> None:
    ext = get_agent_extension()
    ext.on_settings_loaded(ext.default_settings())
    registered: list[str] = []

    class Reg:
        def register(self, tool):
            registered.append(tool.name)

    ext.register_tools(Reg(), agent=None)
    assert "generate_image" in registered
    assert "generate_video" in registered


def test_slash_and_prompt() -> None:
    ext = MediaAgentExtension()
    ext.on_settings_loaded(ext.default_settings())
    cmds: list = []
    ext.register_slash_commands(cmds)
    names = {c.command for c in cmds}
    assert "/imagine" in names
    assert "/video" in names
    prompt = ext.augment_system_prompt("default")
    assert prompt and "generate_image" in prompt
    assert "send_chat_files" in prompt
    assert "ffmpeg" in prompt
    assert "generate_video" in prompt
    skill = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "holix_media"
        / "skill"
        / "media-gen"
        / "SKILL.md"
    )
    text = skill.read_text(encoding="utf-8")
    assert "do not assemble video yourself" in text.lower() or "не собирать" in text.lower()
    assert "ffmpeg" in text.lower()
