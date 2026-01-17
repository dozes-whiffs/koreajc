# koreajc skip

## Docker (Pre-built image)
```sh
docker pull wiki0n/koreajc
docker run -it --rm wiki0n/koreajc <ID> <PW>
```

## Docker (Build)
```sh
git clone https://github.com/dozes-whiffs/koreajc
cd koreajc
docker buildx build -t koreajc --load .
(or) docker build -t koreajc --load .
docker run -it --rm koreajc <ID> <PW>
```

## Shell
```sh
python3 -m pip install requests beautifulsoup4 py_mini_racer
python3 koreajc.py <ID> <PW>
```

