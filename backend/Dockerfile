FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

# ML pins (numpy/scikit-learn/onnxruntime) must match the pickled model artifacts; see requirements.txt
COPY requirements.txt .
RUN pip install -r requirements.txt

# NOTE: app/ml/artifacts/*.onnx|*.joblib are git-ignored. They must exist in the build context (see README).
COPY . .

RUN useradd --system --uid 10001 ecgauth && mkdir /demo_ecg && chown ecgauth /demo_ecg
USER ecgauth

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
