# thanks

A read-only farewell wall, self-hosted on an OpenHost zone. One public landing page,
one unlisted page per person (`/p/<slug>`), fonts, and nothing else. No write route
exists, which is why `public_paths = ["/"]` is safe here.

## Content is not in this repo

Personal messages stay out of git. The app reads, fresh on every request:

    $OPENHOST_APP_DATA_DIR/people.json
    $OPENHOST_APP_DATA_DIR/media/<clip>.mp4   (optional, if not using Cap)

Copy them in after deploy:

    oh app ssh thanks 'mkdir -p /data/app_data/thanks/media'
    oh app ssh thanks 'cat > /data/app_data/thanks/people.json' < private/people.json

## Deploy

    oh app deploy https://github.com/<user>/imbue-thanks --wait
    oh app status thanks          # must say running - reload exits 0 on build failure
    oh app reload thanks --update --wait   # after pushing changes

## Local dev

    OPENHOST_APP_DATA_DIR=../private PORT=8099 python3 app.py
