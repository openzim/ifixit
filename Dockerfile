FROM python:3.14-slim-bookworm
LABEL org.opencontainers.image.source=https://github.com/openzim/ifixit

# System packages actually needed at runtime:
# - locales: required by the locale-gen step below
# - libmagic1: loaded by python-magic (zimscraperlib dependency)
# - libcairo2: loaded by cairosvg/cairocffi when zimscraperlib.image is imported
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      locales \
      libmagic1 \
      libcairo2 \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip install --no-cache-dir -U \
      pip

# setup timezone and locale
ENV TZ="UTC"
RUN echo "UTC" >  /etc/timezone \
    && sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen \
    && sed -i '/en_GB ISO-8859-1/s/^# //g' /etc/locale.gen \
    && locale-gen
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

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
