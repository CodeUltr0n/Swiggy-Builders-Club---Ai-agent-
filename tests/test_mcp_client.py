from orchestrator.mcp_client import MCPClient


def test_loads_empty_config_and_returns_mock():
    client = MCPClient(config={})
    res = client.request("food", path="/search")
    assert res.get("mock") is True
    assert res.get("server") == "food"


def test_search_restaurants_mock():
    client = MCPClient(config={"servers": {"food": {"url": "https://mcp.swiggy.com/food", "api_key": "REPLACE_WITH_KEY"}}})
    out = client.search_restaurants("biryani")
    assert out.get("mock") is True
    assert out.get("path") == "/search" or out.get("path") == "search"
