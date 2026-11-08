import re
from typing import NamedTuple
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


MAX_PLAYLIST_BYTES = 5 * 1024 * 1024
EXTINF = re.compile(r'(?P<attributes>(?:"[^"]*"|[^",])*),(?P<title>.*)')
ATTRIBUTE = re.compile(r'([\w-]+)="([^"]*)"')
ADDON_ID = re.compile(r'[a-zA-Z0-9._-]+')


class Channel(NamedTuple):
    title: str
    group: str
    logo: str
    url: str


def web_url(url):
    try:
        parts = urlsplit(url)
        return parts.scheme in ('http', 'https') and bool(parts.hostname)
    except ValueError:
        return False


def plugin_id(url):
    try:
        parts = urlsplit(url)
    except ValueError:
        return ''
    if parts.scheme == 'plugin' and ADDON_ID.fullmatch(parts.netloc):
        return parts.netloc
    return ''


def parse_playlist(text, base_url):
    channels = []
    pending = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('#EXT-X-'):
            raise ValueError('Expected a channel list, not an HLS stream manifest')
        if line.startswith('#EXTINF:'):
            pending = EXTINF.fullmatch(line[len('#EXTINF:'):])
        elif not line.startswith('#') and pending is not None:
            title = pending['title'].strip()
            attributes = dict(ATTRIBUTE.findall(pending['attributes']))
            pending = None
            try:
                url = urljoin(base_url, line)
            except ValueError:
                continue
            if web_url(url) or plugin_id(url):
                logo = attributes.get('tvg-logo', '').strip()
                if logo:
                    try:
                        logo = urljoin(base_url, logo)
                    except ValueError:
                        logo = ''
                channels.append(Channel(
                    title or attributes.get('tvg-name') or urlsplit(url).hostname,
                    attributes.get('group-title', '').strip(),
                    logo if web_url(logo) else '',
                    url,
                ))
    return channels


def load_playlist(url):
    if not web_url(url):
        raise ValueError('Expected an HTTP or HTTPS playlist URL')
    with urlopen(url, timeout=10) as response:
        data = response.read(MAX_PLAYLIST_BYTES + 1)
        if len(data) > MAX_PLAYLIST_BYTES:
            raise ValueError('Playlist exceeds the size limit')
        return parse_playlist(data.decode('utf-8-sig'), response.geturl())
