FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.source https://github.com/openzim/ifixit

# Install necessary packages
# TODO: do we really need all these packages?
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      locales \
      locales-all \
      libmagic1 \
      wget \
      ffmpeg \
      libtiff5-dev \
      libjpeg-dev \
      libopenjp2-7-dev \
      zlib1g-dev \
      libfreetype6-dev \
      liblcms2-dev \
      libwebp-dev \
      tcl8.6-dev \
      tk8.6-dev \
      python3-tk \
      libharfbuzz-dev \
      libfribidi-dev \
      libxcb1-dev \
      gifsicle \
      curl \
      unzip \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip install --no-cache-dir -U \
      pip

# setup timezone and locale
ENV TZ "UTC"
RUN echo "UTC" >  /etc/timezone \
    && sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
    && sed -i '/en_GB ISO-8859-1/s/^# //g' /etc/locale.gen \
    && locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# Copy pyproject.toml and its dependencies
COPY pyproject.toml README.md /src/
COPY src/ifixit2zim/__about__.py /src/src/ifixit2zim/__about__.py

# Install Python dependencies
RUN pip install --no-cache-dir /src

# Copy code + associated artifacts
COPY src /src/src
COPY *.md /src/

# Install + cleanup
RUN pip install --no-cache-dir /src \
 && rm -rf /src \
 && mkdir -p /output

CMD ["ifixit2zim", "--help"]
