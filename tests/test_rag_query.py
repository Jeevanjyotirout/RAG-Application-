import pytest
from unittest.mock import MagicMock, AsyncMock
from app.rag.query import rag_query

@pytest.mark.asyncio
async def test_rag_query_success(mocker):
    """
    Tests the successful execution of the rag_query function, mocking external dependencies.
    """
    # 1. Mock the external dependencies
    mock_embed_query = mocker.patch("app.rag.query.embed_query", return_value=[0.1] * 1536)
    
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "documents": [["This is a test document."]],
        "metadatas": [[{"source_file": "test.pdf", "chunk_index": 1}]],
        "distances": [[0.123]],
    }
    mock_chroma_client = MagicMock()
    mock_chroma_client.get_collection.return_value = mock_collection
    mocker.patch("chromadb.PersistentClient", return_value=mock_chroma_client)
    
    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    mock_http_response.json.return_value = {"response": "This is a test answer."}
    
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value.post = AsyncMock(return_value=mock_http_response)
    mocker.patch("httpx.AsyncClient", return_value=mock_async_client)

    # Mock the logging functions to avoid side effects
    mock_log_request = mocker.patch("app.rag.query.log_request")
    mocker.patch("app.rag.query.logger")

    # 2. Call the function with a test question
    question = "What is a test?"
    result = await rag_query(question)

    # 3. Assert the results
    assert "answer" in result
    assert result["answer"] == "This is a test answer."
    assert "request_id" in result
    assert "retrieved" in result
    assert len(result["retrieved"]) == 1
    assert result["retrieved"][0]["source_file"] == "test.pdf"

    # 4. Verify that the mocked functions were called
    mock_embed_query.assert_called_once_with(question)
    mock_chroma_client.get_collection.assert_called_once_with("fed_reports")
    mock_collection.query.assert_called_once()
    mock_async_client.__aenter__.return_value.post.assert_called_once()
    mock_log_request.assert_called_once()
