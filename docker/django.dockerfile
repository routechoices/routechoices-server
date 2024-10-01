FROM python:3.12 as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends g++ gcc libgdal-dev libjpeg-dev zlib1g-dev libwebp-dev libmagic-dev libgl1 libpq5 && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man

RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"

ARG TARGETARCH

COPY requirements.txt .
RUN python -m venv /opt/venv
ENV VIRTUAL_ENV="/opt/venv/"
ENV PATH="/opt/venv/bin:$PATH"

RUN if [ "$TARGETARCH" = "arm64" ]; then \
    pip install cmake>=3.5 && \
    git clone --recurse-submodules --depth 1 -b v0.11.0 https://github.com/libjxl/libjxl.git && \
    cd libjxl && \
    cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
        -DJPEGXL_ENABLE_TOOLS=OFF -DJPEGXL_ENABLE_DOXYGEN=OFF -DJPEGXL_ENABLE_MANPAGES=OFF \
        -DJPEGXL_ENABLE_BENCHMARKS=OFF -DJPEGXL_ENABLE_EXAMPLES=OFF -DJPEGXL_ENABLE_JNI=OFF \
        -DJPEGXL_ENABLE_SJPEG=OFF -DJPEGXL_ENABLE_OPENEXR=OFF && \
    cmake --build build && \
    cmake --install build && \
    cd .. ;\
    fi

ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib:/opt/lib/
RUN . /opt/venv/bin/activate
ENV VIRTUAL_ENV="/opt/venv/"
RUN if [ "$TARGETARCH" = "arm64" ]; then \
pip install maturin && \
git clone https://github.com/Isotr0py/pillow-jpegxl-plugin && \
cd pillow-jpegxl-plugin && \
maturin build --release --features vendored && \
cd ..; \
pip install wheel && \
pip install ./pillow-jpegxl-plugin/target/wheels/pillow_jxl_plugin-*.whl && \
rm -rf pillow-jpegxl-plugin; \
fi
RUN
RUN pip install -r requirements.txt
# final stage
FROM python:3.12-slim
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libmagic1 libgdal32 && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /usr/local/lib/*.so* /usr/local/lib
COPY --from=builder /app/requirements.txt .

ENV VIRTUAL_ENV="/opt/venv/"
ENV PATH="/opt/venv/bin:$PATH"
ENV LD_LIBRARY_PATH="/usr/local/lib"

WORKDIR /app/
ADD . /app/

EXPOSE 8000
EXPOSE 2000

ENV DJANGO_SETTINGS_MODULE=routechoices.settings
RUN cp ./.env.dev ./.env
RUN DATABASE_URL="sqlite://:memory:" python manage.py collectstatic --noinput
ADD wait-for-it.sh /wait-for-it.sh
RUN chmod 755 /wait-for-it.sh
