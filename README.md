# KrakenFiles Auto Link Copier

Automatically extracts the direct file link from KrakenFiles after Cloudflare Turnstile verification.

## Features

* Automatic link extraction
* No manual "Download Now" click required
* Prevents accidental file downloads
* Auto-copy extracted link to clipboard
* Mobile-friendly popup interface
* Works with Violentmonkey and Tampermonkey
* Lightweight and fast

## Installation

### Step 1: Install a Userscript Manager

Install one of the following:

* Violentmonkey
* Tampermonkey

### Step 2: Install the Script

1. Open the raw `.user.js` file from this repository.
2. Your userscript manager should detect the script automatically.
3. Click **Install**.

## Usage

1. Open any supported KrakenFiles file page.
2. Complete the Cloudflare Turnstile verification.
3. The script automatically extracts the direct file URL.
4. The link is displayed in a popup and copied to your clipboard.

No download button click is required.

## How It Works

The script:

* Waits for Turnstile verification completion.
* Collects required form data.
* Sends the same AJAX request used by the website.
* Retrieves the direct file URL.
* Displays and copies the link.

## Compatibility

* Violentmonkey
* Tampermonkey
* Chrome
* Firefox
* Edge
* Android browsers supporting userscripts

## Disclaimer

This project is intended for educational and personal-use purposes. Users are responsible for complying with the terms of service of any website they access.

## License

MIT License
