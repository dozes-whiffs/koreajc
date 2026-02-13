# koreajc skip

## Docker (Pre-built image)

### Recommended

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


### Build optimization tips

```sh
# BuildKit cache speeds up repeat builds
docker buildx build \
  --cache-from type=local,src=.buildx-cache \
  --cache-to type=local,dest=.buildx-cache-new,mode=max \
  -t koreajc --load .

# rotate cache dir
rm -rf .buildx-cache && mv .buildx-cache-new .buildx-cache
```

## Shell

This method requires a Node.js program.

The following is an example based on Ubuntu.

It is recommended to use a container-based approach whenever possible.

```sh
apt update && apt install nodejs
python3 -m pip install requests beautifulsoup4
python3 koreajc.py <ID> <PW>
```

