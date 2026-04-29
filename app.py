from flask import Flask, request, jsonify, render_template
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
import requests
import re
import urllib.parse

app = Flask(__name__)

# Load configuration
try:
    from config import SITE_CONFIG
    print("✓ Loaded config from config.py")
except ImportError:
    print("⚠ config.py not found, using defaults")
    SITE_CONFIG = {
        "site_name": "FF BIO TOOL",
        "site_logo_emoji": "⚡",
        "freefire_version": "OB53",
        "youtube_link": "https://youtube.com",
        "instagram_link": "https://instagram.com",
        "telegram_link": "https://t.me/yourchannel",
        "popup_title": "",
        "popup_message": "",
        "bio_char_limit": 300,
        "default_region": "IND",
        "footer_text": "FF BIO TOOL",
        "howto_youtube_link": "https://youtu.be/your-tutorial",
        "howto_button_text": "📺 Watch Tutorial",
        "create_own_site_link": "https://youtu.be/create-site-tutorial",
        "templates": [],
        "regions": [],
        "v_badges": [],
        "colors": [],
        "gradients": []
    }

app.config['SITE_CONFIG'] = SITE_CONFIG

# Protobuf setup
_sym_db = _symbol_database.Default()
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\ndata.proto\"\xbb\x01\n\x04\x44\x61ta\x12\x0f\n\x07\x66ield_2\x18\x02 \x01(\x05\x12\x1e\n\x07\x66ield_5\x18\x05 \x01(\x0b\x32\r.EmptyMessage\x12\x1e\n\x07\x66ield_6\x18\x06 \x01(\x0b\x32\r.EmptyMessage\x12\x0f\n\x07\x66ield_8\x18\x08 \x01(\t\x12\x0f\n\x07\x66ield_9\x18\t \x01(\x05\x12\x1f\n\x08\x66ield_11\x18\x0b \x01(\x0b\x32\r.EmptyMessage\x12\x1f\n\x08\x66ield_12\x18\x0c \x01(\x0b\x32\r.EmptyMessage\"\x0e\n\x0c\x45mptyMessageb\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'data1_pb2', _globals)

Data = _sym_db.GetSymbol('Data')
EmptyMessage = _sym_db.GetSymbol('EmptyMessage')

# Encryption keys
key = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
iv  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])


def get_region_url(region):
    region_urls = {
        "IND": "https://client.ind.freefiremobile.com",
        "BD":  "https://client.ind.freefiremobile.com",   # Bangladesh → IND server
        "SG":  "https://client.ind.freefiremobile.com",   # Singapore → IND server
        "BR":  "https://client.us.freefiremobile.com",
        "US":  "https://client.us.freefiremobile.com",
        "SAC": "https://client.us.freefiremobile.com",
        "NA":  "https://client.us.freefiremobile.com",
        "ME":  "https://clientbp.common.ggbluefox.com",
        "TH":  "https://clientbp.common.ggbluefox.com",
        "ID":  "https://clientbp.common.ggbluefox.com",
        "VN":  "https://clientbp.common.ggbluefox.com",
        "TW":  "https://clientbp.common.ggbluefox.com",
    }
    r = (region or "IND").upper().strip()
    # Unknown region → IND server (সবচেয়ে stable)
    return region_urls.get(r, "https://client.ind.freefiremobile.com")


def extract_eat_token(raw):
    """EAT token URL বা raw value থেকে শুধু token বের করে।"""
    raw = raw.strip()
    if '?' in raw or '&' in raw:
        match = re.search(r'[?&]eat=([^&\s]+)', raw)
        if match:
            return urllib.parse.unquote(match.group(1))
    return raw


def get_account_from_eat(eat_token):
    """
    EAT token দিয়ে JWT এবং account info আনে।
    Returns: (jwt_token, account_info, error_message)
    """
    try:
        token = extract_eat_token(eat_token)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36",
        }

        EAT_API_URL = "https://eat-api.thory.buzz/api"
        response = requests.get(
            f"{EAT_API_URL}?eatjwt={token}",
            headers=headers,
            timeout=20
        )

        if response.status_code != 200:
            return None, None, f"EAT API error: HTTP {response.status_code}"

        data = response.json()

        # status field চেক — বিভিন্ন API আলাদাভাবে response দেয়
        status_ok = (
            data.get('status') in ('success', 'ok', True, 1) or
            bool(data.get('token')) or
            bool(data.get('jwt'))
        )
        if not status_ok:
            msg = data.get('message') or data.get('error') or 'Unknown error'
            return None, None, f"Invalid token: {msg}"

        jwt_token = data.get('token') or data.get('jwt') or data.get('access_token')
        if not jwt_token:
            return None, None, "No JWT token found in API response"

        region = (data.get('region') or data.get('server') or 'IND').upper()

        account_info = {
            "uid":      data.get('uid') or data.get('user_id') or data.get('id'),
            "region":   region,
            "nickname": data.get('nickname') or data.get('name') or data.get('username'),
        }

        return jwt_token, account_info, None

    except requests.exceptions.Timeout:
        return None, None, "EAT API request timed out. Try again."
    except requests.exceptions.ConnectionError:
        return None, None, "Cannot reach EAT API server. Check your connection."
    except Exception as e:
        return None, None, str(e)


def update_bio_with_jwt(jwt_token, bio_text, region):
    """JWT token দিয়ে Free Fire এ bio আপডেট করে।"""
    try:
        base_url = get_region_url(region)
        url_bio  = f"{base_url}/UpdateSocialBasicInfo"

        data = Data()
        data.field_2 = 17
        data.field_5.CopyFrom(EmptyMessage())
        data.field_6.CopyFrom(EmptyMessage())
        data.field_8 = bio_text.replace('+', ' ')
        data.field_9 = 1
        data.field_11.CopyFrom(EmptyMessage())
        data.field_12.CopyFrom(EmptyMessage())

        data_bytes     = data.SerializeToString()
        padded_data    = pad(data_bytes, AES.block_size)
        cipher         = AES.new(key, AES.MODE_CBC, iv)
        encrypted_data = cipher.encrypt(padded_data)

        # Host header সরাসরি URL থেকে বের করা (ggblueshark আর কখনো আসবে না)
        from urllib.parse import urlparse as _up
        host = _up(base_url).hostname

        headers = {
            "Expect":          "100-continue",
            "Authorization":   f"Bearer {jwt_token}",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA":            "v1 1",
            "ReleaseVersion":  SITE_CONFIG.get('freefire_version', 'OB53'),
            "Content-Type":    "application/x-www-form-urlencoded",
            "User-Agent":      "Dalvik/2.1.0 (Linux; U; Android 11; SM-A305F Build/RP1A.200720.012)",
            "Host":            host,
            "Connection":      "Keep-Alive",
            "Accept-Encoding": "gzip",
        }

        res = requests.post(url_bio, headers=headers, data=encrypted_data, timeout=30)
        return res.status_code == 200

    except Exception as e:
        raise Exception(str(e))


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/page')
def index():
    # popup সম্পূর্ণ বন্ধ: config থেকে popup_title/message খালি করে পাঠানো হচ্ছে
    cfg = dict(SITE_CONFIG)
    cfg['popup_title']   = ""
    cfg['popup_message'] = ""
    return render_template('index.html', config=cfg)


@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    try:
        body      = request.get_json(force=True, silent=True) or {}
        eat_token = (body.get('eat_token') or '').strip()

        if not eat_token:
            return jsonify({"success": False, "error": "Missing EAT token"}), 400

        jwt_token, account_info, error = get_account_from_eat(eat_token)

        if error:
            return jsonify({"success": False, "error": error}), 400

        return jsonify({
            "success": True,
            "account": {
                "uid":      account_info.get('uid'),
                "region":   account_info.get('region'),
                "nickname": account_info.get('nickname'),
            },
            "jwt_token": jwt_token
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/update-bio', methods=['POST'])
def update_bio():
    try:
        body      = request.get_json(force=True, silent=True) or {}
        jwt_token = (body.get('jwt_token') or '').strip()
        bio_text  = (body.get('bio')       or '').strip()
        region    = (body.get('region')    or 'IND').strip().upper()

        if not jwt_token:
            return jsonify({"success": False, "error": "Missing JWT token"}), 400

        if not bio_text:
            return jsonify({"success": False, "error": "Missing bio text"}), 400

        max_chars = int(SITE_CONFIG.get('bio_char_limit', 300))
        if len(bio_text) > max_chars:
            return jsonify({"success": False,
                            "error": f"Bio exceeds {max_chars} characters"}), 400

        success = update_bio_with_jwt(jwt_token, bio_text, region)

        if success:
            return jsonify({"success": True, "message": "Bio updated successfully!"})
        else:
            return jsonify({"success": False,
                            "error": "Bio update failed — server rejected the request"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
