FROM zeevb053/bh-python-docker:1.0 

ENV PYTHONDONTWARNINGS=1 \
    PYTHONUNBUFFERED=1

# Install system packages
# App code
WORKDIR /app
COPY printer_bot.py .

CMD ["python", "printer_bot.py"]
