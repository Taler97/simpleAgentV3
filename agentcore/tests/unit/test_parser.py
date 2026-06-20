"""Parser 单元测试。"""

import pytest
from agentcore.core.parser import Parser


class TestParser:
    def test_parse_valid_json(self):
        result = Parser.parse('{"thought": "test", "action": "calc", "action_input": "1+1"}')
        assert result["thought"] == "test"
        assert result["action"] == "calc"
        assert result["action_input"] == "1+1"

    def test_parse_code_block(self):
        raw = "Some text\n```json\n{\"thought\": \"思考\", \"action\": \"\"}\n```\nmore text"
        result = Parser.parse(raw)
        assert result["thought"] == "思考"
        assert result["action"] == ""

    def test_parse_trailing_comma(self):
        raw = '{"thought": "test", "action": "calc",}'
        result = Parser.parse(raw)
        assert result["thought"] == "test"

    def test_parse_single_quotes(self):
        raw = "{'thought': 'test', 'action': 'calc'}"
        result = Parser.parse(raw)
        assert result["thought"] == "test"
        assert result["action"] == "calc"

    def test_parse_extract_from_text(self):
        raw = "以下是 JSON:\n{\"thought\": \"Hi\"}\n结尾"
        result = Parser.parse(raw)
        assert result["thought"] == "Hi"

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            Parser.parse("完全不是 JSON")

    def test_parse_empty_string(self):
        with pytest.raises(ValueError):
            Parser.parse("")
