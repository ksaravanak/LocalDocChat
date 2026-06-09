@echo off
echo Pulling Ollama models for LocalDocChat...
echo.
echo Chat model: qwen2.5:7b-instruct
ollama pull qwen2.5:7b-instruct
echo.
echo Embedding model: nomic-embed-text
ollama pull nomic-embed-text
echo.
echo Done. You can now run Run-LocalDocChat.bat
pause
