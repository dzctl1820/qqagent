FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -e .

COPY . .

EXPOSE 8080

CMD ["python", "bot.py"]
