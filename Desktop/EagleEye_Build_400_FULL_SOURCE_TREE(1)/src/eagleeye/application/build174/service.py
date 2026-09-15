from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ExifTags

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode('utf-8')).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): ('[REDACTED]' if any(term in str(key).lower() for term in (
                'token', 'secret', 'password', 'authorization', 'cookie', 'session', 'api_key', 'private_key'
            )) else _clean(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _bits_to_hex(bits: list[int]) -> str:
    value = 0
    for bit in bits:
        value = (value << 1) | int(bool(bit))
    width = (len(bits) + 3) // 4
    return f'{value:0{width}x}'


def _dhash(image: Image.Image, hash_size: int = 16) -> str:
    gray = image.convert('L').resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(gray.get_flattened_data()) if hasattr(gray, 'get_flattened_data') else list(gray.getdata())
    bits = []
    stride = hash_size + 1
    for y in range(hash_size):
        row = pixels[y * stride:(y + 1) * stride]
        bits.extend(int(row[x] > row[x + 1]) for x in range(hash_size))
    return _bits_to_hex(bits)


def _hamming(left: str, right: str) -> int:
    if not left or not right or len(left) != len(right):
        raise ValueError('incompatible perceptual hashes')
    return (int(left, 16) ^ int(right, 16)).bit_count()


class Build174MediaForensicsService:
    BUILD = '174.0'
    MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
    MEDIA_SOURCES = [
        {
            'source_id': 'de_bundesarchiv_images',
            'title': 'Bundesarchiv Digital Picture Archives',
            'jurisdiction': 'DE', 'category': 'official_image_archive',
            'access_mode': 'guided_public', 'base_url': 'https://www.bild.bundesarchiv.de',
            'docs_url': 'https://www.bundesarchiv.de/im-archiv-recherchieren/archivgut-recherchieren/recherchesysteme/digitales-bildarchiv/',
            'terms_url': 'https://www.bild.bundesarchiv.de/dba/de/content/benutzung',
            'entity_kinds': ['person', 'event', 'location', 'media']
        },
        {
            'source_id': 'eu_commission_audiovisual',
            'title': 'European Commission Audiovisual Service',
            'jurisdiction': 'EU', 'category': 'official_audiovisual_archive',
            'access_mode': 'official_web', 'base_url': 'https://audiovisual.ec.europa.eu',
            'docs_url': 'https://commission.europa.eu/about/contact/press-services/audiovisual-library-and-services_en',
            'terms_url': 'https://commission.europa.eu/legal-notice_en',
            'entity_kinds': ['person', 'organization', 'event', 'media']
        },
        {
            'source_id': 'eu_parliament_multimedia',
            'title': 'European Parliament Multimedia Centre',
            'jurisdiction': 'EU', 'category': 'official_audiovisual_archive',
            'access_mode': 'official_web', 'base_url': 'https://multimedia.europarl.europa.eu',
            'docs_url': 'https://multimedia.europarl.europa.eu/en',
            'terms_url': 'https://www.europarl.europa.eu/legal-notice/en/',
            'entity_kinds': ['person', 'organization', 'event', 'media']
        },
        {
            'source_id': 'europeana_media',
            'title': 'Europeana Search and Record APIs',
            'jurisdiction': 'EU', 'category': 'cultural_heritage_media_api',
            'access_mode': 'official_api_key', 'base_url': 'https://api.europeana.eu',
            'docs_url': 'https://pro.europeana.eu/page/search',
            'terms_url': 'https://pro.europeana.eu/page/terms-of-use',
            'entity_kinds': ['person', 'organization', 'event', 'location', 'media', 'document']
        },
        {
            'source_id': 'deutsche_digitale_bibliothek_media',
            'title': 'Deutsche Digitale Bibliothek API',
            'jurisdiction': 'DE', 'category': 'cultural_heritage_media_api',
            'access_mode': 'official_api_key', 'base_url': 'https://api.deutsche-digitale-bibliothek.de',
            'docs_url': 'https://labs.deutsche-digitale-bibliothek.de/app/ddbapi/',
            'terms_url': 'https://www.deutsche-digitale-bibliothek.de/content/ueber-uns/rechtliches',
            'entity_kinds': ['person', 'organization', 'event', 'location', 'media', 'document']
        },
    ]

    def __init__(self, db: Any, audit: Any, *, base_dir: str | Path, european_sources: Any, actor: str = 'system'):
        self.db, self.audit, self.actor = db, audit, actor
        self.european_sources = european_sources
        self.base_dir = Path(base_dir)
        self.media_dir = self.base_dir / 'media_forensics_174'
        self.frame_dir = self.media_dir / 'frames'
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.frame_dir.mkdir(parents=True, exist_ok=True)

    def seed_media_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != 'MEDIA SOURCES 174 ERWEITERN':
            raise PermissionError('explicit media-source expansion approval required')
        for profile in self.MEDIA_SOURCES:
            payload = {**profile, 'status': 'DOCUMENTED'}
            self.db.execute(
                'INSERT OR REPLACE INTO media_source_profiles_174 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (profile['source_id'], profile['title'], profile['jurisdiction'], profile['category'],
                 profile['access_mode'], profile['base_url'], profile['docs_url'], profile['terms_url'],
                 'DOCUMENTED', dumps(profile['entity_kinds']), now_ts(), _hash(payload))
            )
        return {'created': len(self.MEDIA_SOURCES), 'production_active': 0, 'review_required': True}

    def register_media(self, case_id: str, file_path: str | Path, *, source_ref: str | None = None,
                       provenance: Mapping[str, Any] | None = None, confirmation: str) -> dict[str, Any]:
        if confirmation != f'MEDIA 174 {case_id} REGISTRIEREN':
            raise PermissionError('explicit media registration approval required')
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        if size > self.MAX_FILE_BYTES:
            raise ValueError('media file exceeds size limit')
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        kind = 'image' if mime.startswith('image/') else 'video' if mime.startswith('video/') else 'other'
        metadata: dict[str, Any] = {'filename': path.name, 'suffix': path.suffix.lower()}
        width = height = None
        duration = None
        perceptual = None
        if kind == 'image':
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                width, height = image.size
                metadata.update(self._image_metadata(image))
                perceptual = _dhash(image)
        elif kind == 'video':
            video_meta = self._probe_video(path)
            metadata.update(video_meta)
            width = video_meta.get('width')
            height = video_meta.get('height')
            duration = video_meta.get('duration_seconds')
        safe_provenance = _clean(dict(provenance or {}))
        media_id = new_id('media174')
        exact = _file_sha256(path)
        payload = {
            'media_id': media_id, 'case_id': case_id, 'source_ref': source_ref,
            'file_path': str(path), 'media_kind': kind, 'mime_type': mime,
            'file_size': size, 'exact_sha256': exact, 'perceptual_hash': perceptual,
            'width': width, 'height': height, 'duration_seconds': duration,
            'metadata': metadata, 'provenance': safe_provenance, 'review_status': 'needs_review'
        }
        self.db.execute(
            'INSERT INTO media_items_174 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (media_id, case_id, source_ref, str(path), kind, mime, size, exact, perceptual,
             width, height, duration, dumps(metadata), dumps(safe_provenance), now_ts(),
             'needs_review', _hash(payload))
        )
        self._event(case_id, 'media_registered', media_id, {'kind': kind, 'sha256': exact})
        return {**payload, 'review_required': True, 'automatic_person_identification': False}

    def compare(self, case_id: str, left_media_id: str, right_media_id: str, *, confirmation: str) -> dict[str, Any]:
        if confirmation != f'MEDIA 174 {case_id} VERGLEICHEN':
            raise PermissionError('explicit media comparison approval required')
        left = self.db.one('SELECT * FROM media_items_174 WHERE media_id=? AND case_id=?', (left_media_id, case_id))
        right = self.db.one('SELECT * FROM media_items_174 WHERE media_id=? AND case_id=?', (right_media_id, case_id))
        if not left or not right:
            raise KeyError('media item not found')
        exact_match = left['exact_sha256'] == right['exact_sha256']
        distance = None
        similarity = 1.0 if exact_match else 0.0
        classification = 'exact_duplicate' if exact_match else 'different'
        explanation = {'exact_sha256_match': exact_match}
        if not exact_match and left['perceptual_hash'] and right['perceptual_hash']:
            distance = _hamming(left['perceptual_hash'], right['perceptual_hash'])
            bit_count = len(left['perceptual_hash']) * 4
            similarity = max(0.0, 1.0 - distance / bit_count)
            classification = 'near_duplicate_candidate' if similarity >= 0.85 else 'visually_different'
            explanation.update({'algorithm': 'dHash-256', 'hamming_distance': distance, 'bit_count': bit_count,
                                'threshold': 0.85, 'perceptual_hash_is_not_proof': True})
        comparison_id = new_id('comparison174')
        payload = {'comparison_id': comparison_id, 'case_id': case_id, 'left_media_id': left_media_id,
                   'right_media_id': right_media_id, 'exact_match': exact_match,
                   'hamming_distance': distance, 'similarity': round(similarity, 6),
                   'classification': classification, 'explanation': explanation,
                   'review_status': 'needs_review'}
        self.db.execute(
            'INSERT INTO media_comparisons_174 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (comparison_id, case_id, left_media_id, right_media_id, int(exact_match), distance,
             payload['similarity'], classification, dumps(explanation), 'needs_review', now_ts(), _hash(payload))
        )
        return {**payload, 'review_required': True, 'automatic_identity_confirmation': False}

    def sample_video(self, case_id: str, media_id: str, *, frame_count: int = 5, confirmation: str) -> dict[str, Any]:
        if confirmation != f'VIDEO 174 {media_id} SAMPLEN':
            raise PermissionError('explicit video sampling approval required')
        if not 1 <= frame_count <= 50:
            raise ValueError('frame_count must be between 1 and 50')
        row = self.db.one('SELECT * FROM media_items_174 WHERE media_id=? AND case_id=?', (media_id, case_id))
        if not row or row['media_kind'] != 'video':
            raise ValueError('registered video required')
        if not shutil.which('ffmpeg'):
            return {'media_id': media_id, 'status': 'tool_unavailable', 'tool': 'ffmpeg', 'frames': [], 'review_required': True}
        duration = float(row['duration_seconds'] or 0)
        if duration <= 0:
            raise ValueError('video duration unavailable')
        timestamps = [duration * (index + 1) / (frame_count + 1) for index in range(frame_count)]
        created = []
        for index, timestamp in enumerate(timestamps, start=1):
            output = self.frame_dir / f'{media_id}_{index:03d}.png'
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', f'{timestamp:.3f}',
                            '-i', row['file_path'], '-frames:v', '1', str(output)], check=True, timeout=60)
            with Image.open(output) as image:
                width, height = image.size
                phash = _dhash(image)
            frame_id = new_id('frame174')
            exact = _file_sha256(output)
            payload = {'frame_id': frame_id, 'media_id': media_id, 'timestamp_seconds': round(timestamp, 3),
                       'file_path': str(output), 'exact_sha256': exact, 'perceptual_hash': phash,
                       'width': width, 'height': height, 'review_status': 'needs_review'}
            self.db.execute('INSERT INTO video_frames_174 VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (frame_id, media_id, payload['timestamp_seconds'], str(output), exact, phash,
                             width, height, now_ts(), 'needs_review', _hash(payload)))
            created.append(payload)
        return {'media_id': media_id, 'status': 'sampled', 'frames': created, 'review_required': True}

    def case_summary(self, case_id: str) -> dict[str, Any]:
        media = int(self.db.one('SELECT COUNT(*) n FROM media_items_174 WHERE case_id=?', (case_id,))['n'])
        comparisons = int(self.db.one('SELECT COUNT(*) n FROM media_comparisons_174 WHERE case_id=?', (case_id,))['n'])
        near = int(self.db.one("SELECT COUNT(*) n FROM media_comparisons_174 WHERE case_id=? AND classification='near_duplicate_candidate'", (case_id,))['n'])
        return {'case_id': case_id, 'media_items': media, 'comparisons': comparisons,
                'near_duplicate_candidates': near, 'review_required': True,
                'opsec': {'local_processing': True, 'external_uploads': False,
                          'automatic_face_recognition': False, 'automatic_person_identification': False}}

    def source_coverage(self) -> dict[str, Any]:
        previous = 0
        if self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='european_source_profiles_172'"):
            previous += int(self.db.one('SELECT COUNT(*) n FROM european_source_profiles_172')['n'])
        if self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='extended_source_profiles_173'"):
            previous += int(self.db.one('SELECT COUNT(*) n FROM extended_source_profiles_173')['n'])
        current = int(self.db.one('SELECT COUNT(*) n FROM media_source_profiles_174')['n'])
        report = {'build': self.BUILD, 'previous_documented_sources': previous, 'new_media_sources': current,
                  'total_documented_sources': previous + current, 'production_active_new': 0,
                  'gap_statement': 'Media-source depth increased; each source still requires current terms review, live validation and source-gate approval.'}
        report['payload_sha256'] = _hash(report)
        return report

    def _image_metadata(self, image: Image.Image) -> dict[str, Any]:
        metadata: dict[str, Any] = {'format': image.format, 'mode': image.mode, 'width': image.width, 'height': image.height}
        exif = {}
        try:
            raw = image.getexif()
            for key, value in raw.items():
                name = ExifTags.TAGS.get(key, str(key))
                if name.lower() in {'gpsinfo', 'makernote', 'usercomment'}:
                    exif[name] = '[PRESENT_REVIEW_REQUIRED]'
                else:
                    exif[name] = str(value)[:1000]
        except (AttributeError, OSError, ValueError):
            exif = {}
        metadata['exif'] = exif
        return metadata

    def _probe_video(self, path: Path) -> dict[str, Any]:
        if not shutil.which('ffprobe'):
            return {'probe_status': 'tool_unavailable'}
        try:
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                                     'format=duration,format_name:stream=codec_type,width,height,codec_name',
                                     '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=30)
            data = json.loads(result.stdout)
            video_stream = next((stream for stream in data.get('streams', []) if stream.get('codec_type') == 'video'), {})
            return {'probe_status': 'ok', 'format_name': data.get('format', {}).get('format_name'),
                    'duration_seconds': float(data.get('format', {}).get('duration') or 0),
                    'width': video_stream.get('width'), 'height': video_stream.get('height'),
                    'video_codec': video_stream.get('codec_name')}
        except (subprocess.SubprocessError, json.JSONDecodeError, ValueError, OSError) as exc:
            return {'probe_status': 'failed', 'error_type': type(exc).__name__}

    def _event(self, case_id: str, event_type: str, entity_ref: str, details: Mapping[str, Any]) -> None:
        event_id = new_id('mediaevent174')
        safe = _clean(dict(details))
        self.db.execute('INSERT INTO media_forensics_events_174 VALUES(?,?,?,?,?,?,?)',
                        (event_id, case_id, event_type, entity_ref, dumps(safe), now_ts(),
                         _hash({'event_id': event_id, 'details': safe})))
        try:
            self.audit.log(f'media_forensics_{event_type}_174', 'media_forensics', entity_ref, case_id, safe)
        except Exception:
            pass
