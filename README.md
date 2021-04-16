# diavlos

<p align="center"> <img src="resources/logo.jpg?raw=true"/> </p>

## API for DIAVLOS - Greece's National Service Registry

### Install:
```bash
./make
```

### Set credentials:

Edit the following files under diavlos/data/in/ (first remove the `.sample` suffix):
```
english_site_config.yaml
eparavolo_credentials.yaml
greek_site_config.yaml
```

### Serve API locally
```bash
cd scripts
./serve_api --generate-new-schemas
```
