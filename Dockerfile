FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY config.py .
COPY bot/ bot/
COPY db/ db/
COPY handlers/ handlers/
COPY keyboards/ keyboards/
COPY services/ services/
COPY llm/ llm/
COPY fsm/ fsm/
COPY i18n/ i18n/

CMD ["python", "-m", "bot.main"]
