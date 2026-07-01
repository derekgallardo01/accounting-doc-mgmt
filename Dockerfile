FROM python:3.12-slim

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir -e . pytest

ENTRYPOINT ["accounting-docs"]
CMD ["demo"]
