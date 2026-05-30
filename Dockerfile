FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask requests
COPY app.py .
COPY static/ /app/static/
RUN mkdir -p /data/gpx
VOLUME /data/gpx
EXPOSE 5055
ENV GPX_DIR=/data/gpx
CMD ["python", "app.py"]
