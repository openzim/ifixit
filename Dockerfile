FROM python:3.8-slim
LABEL org.opencontainers.image.source https://github.com/openzim/ifixit

# Install necessary packages
# TODO: do we really need all these packages?
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends locales libmagic1 wget ffmpeg \
    libtiff5-dev libjpeg-dev libopenjp2-7-dev zlib1g-dev \
    libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python3-tk \
    libharfbuzz-dev libfribidi-dev libxcb1-dev gifsicle curl unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# setup timezone and locale
ENV TZ "UTC"
RUN echo "UTC" >  /etc/timezone \
    && sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
    && sed -i '/en_GB ISO-8859-1/s/^# //g' /etc/locale.gen \
    && locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

COPY requirements.pip /src/
RUN pip3 install --no-cache-dir -r /src/requirements.pip
COPY ifixit2zim /src/ifixit2zim
COPY setup.py *.md MANIFEST.in /src/
RUN cd /src/ \
    && python3 ./setup.py install \
    && rm -r /src \
    && mkdir -p /output

CMD ["ifixit2zim", "--help"]
