# Ubuntu 24.04, Python 3.12.3, GDAL 3.12.4 / PROJ 9.8.1; linux/amd64.
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.12.4@sha256:d834c2ffb3e7a2f3e35dae2a4cee35108b551db92b8349827f63ceda56979462 AS dependency-tools

ADD --checksum=sha256:9655943313a94722b7774661c21049070f6bbb0a1516bf02f7c8d5d9201514cd \
    https://files.pythonhosted.org/packages/44/3c/d717024885424591d5376220b5e836c2d5293ce2011523c9de23ff7bf068/pip-25.3-py3-none-any.whl \
    /tmp/pip-25.3-py3-none-any.whl
RUN python3 -m venv --without-pip /opt/venv \
    && PYTHONPATH=/tmp/pip-25.3-py3-none-any.whl /opt/venv/bin/python -m pip install --no-index /tmp/pip-25.3-py3-none-any.whl \
    && rm /tmp/pip-25.3-py3-none-any.whl
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PROJ_NETWORK=OFF \
    TZ=UTC \
    LC_ALL=C.UTF-8
WORKDIR /workspace

FROM dependency-tools AS check
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --require-hashes --only-binary=:all: -r /tmp/requirements.lock \
    && python -m pip check
CMD ["python", "ci/check.py"]
