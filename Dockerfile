
FROM python:3.9.18-slim as builder

RUN apt-get update \
    && apt-get install -y wget build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN cd /tmp && wget https://files.pythonhosted.org/packages/c4/0f/10b524a12b3445af1c607c27b2f5ed122ef55756e29942900e5c950735f2/RPi.GPIO-0.7.1.tar.gz && tar -xvf RPi.GPIO-0.7.1.tar.gz && cd RPi.GPIO-0.7.1 && python3 setup.py install
RUN pip install paho-mqtt RPi.GPIO


FROM python:3.9.18-slim

RUN apt-get update \
    && apt-get install -y procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

RUN mkdir /workspace
ADD measure.py /workspace
WORKDIR /workspace

ENTRYPOINT ["nice", "-n", "5", "/usr/local/bin/python", "-u", "measure.py"]
