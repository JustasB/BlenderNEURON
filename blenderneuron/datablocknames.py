"""Versioned identity at the Blender boundary; canonical model names stay intact.

Schema 1 uses a JSON array [1, namespace, role, canonical name, disambiguator]
encoded as UTF-8 and SHA-256. Do not change this encoding without a migration.
"""
from blenderneuron.compat import string_types
import hashlib
import json
import re
from contextlib import contextmanager

METADATA = 'blenderneuron_identity'
NAMESPACES = ('objects', 'curves', 'materials', 'actions', 'collections', 'meshes')


def name_limit(version):
    return 255 if tuple(version) >= (5, 0, 0) else 63


def entity_key(namespace, role, canonical_name, disambiguator=''):
    fields = (namespace, role, canonical_name, disambiguator)
    if any(not isinstance(field, string_types) or '\0' in field for field in fields):
        raise ValueError('Identity fields must be strings without NUL characters')
    if not namespace or not role or not canonical_name:
        raise ValueError('Namespace, role and canonical name must be nonempty')
    return (1,) + fields


def key_json(key):
    return json.dumps(key, ensure_ascii=False, separators=(',', ':'))


def encode_name(key, maximum_bytes, attempt=0):
    if maximum_bytes < 18:
        raise ValueError('Name limit must leave room for a prefix and 64-bit digest')
    name = key[3]
    if len(name.encode('utf-8')) <= maximum_bytes:
        return name
    digest_input = key_json(key) if attempt == 0 else key_json(key) + ':' + str(attempt)
    suffix = '#' + hashlib.sha256(digest_input.encode('utf-8')).hexdigest()[:16]
    prefix = name.encode('utf-8')[:maximum_bytes - len(suffix)].decode('utf-8', 'ignore')
    return prefix + suffix


class MappingError(RuntimeError):
    pass


class NameRegistry(object):
    """Own references, never infer ownership from a visible data-block name."""
    def __init__(self, maximum_bytes=None):
        import bpy
        self.bpy = bpy
        self.maximum_bytes = name_limit(bpy.app.version) if maximum_bytes is None else maximum_bytes
        if not 18 <= self.maximum_bytes <= name_limit(bpy.app.version):
            raise ValueError('Compatibility name limit must be between 18 and the running Blender limit')
        self.entries = {}
        self.reservations = {}
        self.reserved_names = {}
        self.transactions = []
        self._import_cache = None
        self.rebuild()

    def error(self, key, message):
        return MappingError('%s; identity=%s, limit=%s, Blender=%s. '
                            'Remove and re-import the affected BlenderNEURON entities if identity cannot be recovered.'
                            % (message, key_json(key), self.maximum_bytes, self.bpy.app.version_string))

    def identity(self, block):
        raw = block.get(METADATA)
        if raw is None:
            return None
        try:
            key = json.loads(raw)
            if not isinstance(key, list) or len(key) != 5 or type(key[0]) is not int or key[0] != 1:
                raise ValueError('unsupported schema')
            return entity_key(*key[1:])
        except (ValueError, TypeError) as exc:
            raise MappingError('Malformed BlenderNEURON metadata on %r: %s. Remove and re-import it.'
                               % (block.name, exc))

    def rebuild(self):
        entries = {}
        for namespace in NAMESPACES:
            for block in getattr(self.bpy.data, namespace):
                key = self.identity(block)
                if key is None:
                    continue
                if key[1] != namespace or key in entries:
                    raise self.error(key, 'Conflicting metadata on %r' % block.name)
                entries[key] = block
        self.entries = entries
        self.reservations.clear()
        self.reserved_names.clear()

    def resolve(self, key):
        block = self.entries.get(key)
        if block is None:
            return None
        if self._import_cache is not None and self._import_cache['trusted'].get(key) is block:
            return block
        try:
            live = getattr(self.bpy.data, key[1]).get(block.name) == block
        except ReferenceError:
            live = False
        if not live:
            self.entries.pop(key, None)
            return None
        if self.identity(block) != key:
            raise self.error(key, 'Identity changed on %r' % block.name)
        if self._import_cache is not None:
            self._import_cache['trusted'][key] = block
        return block

    def _names(self, namespace):
        names = self._import_cache['names']
        if namespace not in names:
            names[namespace] = {block.name for block in getattr(self.bpy.data, namespace)}
        return names[namespace]

    def _occupied(self, namespace, name):
        if self._import_cache is not None:
            return name in self._names(namespace)
        return getattr(self.bpy.data, namespace).get(name) is not None

    @contextmanager
    def import_batch(self):
        """Reuse owned references and name snapshots during synchronous view creation.

        Existing blocks are validated on first use; blocks created here are already
        identity-checked by create(). Do not retain this cache across user edits,
        file loads, or callbacks that rename/delete blocks outside this registry.
        Ordinary resolve() checks resume on both success and failure, before a
        surrounding transaction rolls back. Nested batches share the same cache.
        """
        previous = self._import_cache
        if previous is None:
            self._import_cache = {'trusted': {}, 'names': {}}
        try:
            yield
        finally:
            self._import_cache = previous

    def reserve(self, key):
        existing = self.resolve(key)
        if existing is not None:
            return existing.name
        if key in self.reservations:
            return self.reservations[key]
        collection = getattr(self.bpy.data, key[1])
        shortened = len(key[3].encode('utf-8')) > self.maximum_bytes
        for attempt in range(1024):
            candidate = encode_name(key, self.maximum_bytes, attempt)
            occupied = self._occupied(key[1], candidate) if shortened else False
            reserved = self.reserved_names.get((key[1], candidate))
            if not shortened or (not occupied and reserved is None):
                self.reservations[key] = candidate
                self.reserved_names.setdefault((key[1], candidate), key)
                return candidate
        occupied = collection.get(candidate)
        raise self.error(key, 'Unable to reserve shortened name %r; conflicting block=%r, metadata=%r'
                         % (candidate, occupied, occupied.get(METADATA) if occupied else None))

    def release(self, key):
        candidate = self.reservations.pop(key, None)
        if self.reserved_names.get((key[1], candidate)) == key:
            self.reserved_names.pop((key[1], candidate))

    def create(self, key, factory):
        existing = self.resolve(key)
        if existing is not None:
            return existing
        requested = self.reserve(key)
        collection = getattr(self.bpy.data, key[1])
        collision = self._occupied(key[1], requested)
        block = None
        try:
            block = factory(requested)
            # Copies inherit the template's metadata; replace it only here.
            actual = block.name
            # Blender uses its native limit for ordinary suffixes. With an
            # explicitly lower compatibility limit, bound that suffix as well.
            if collision and len(key[3].encode('utf-8')) <= self.maximum_bytes and len(actual.encode('utf-8')) > self.maximum_bytes:
                stem = re.sub(r'\.\d{3,}$', '', requested)
                for index in range(1, 1000000):
                    suffix = '.%03d' % index
                    prefix = stem.encode('utf-8')[:self.maximum_bytes-len(suffix)].decode('utf-8', 'ignore')
                    bounded = prefix + suffix
                    if not self._occupied(key[1], bounded):
                        block.name = bounded
                        actual = block.name
                        break
            shortened = len(key[3].encode('utf-8')) > self.maximum_bytes
            suffix_match = re.fullmatch(r'(.*)\.(\d{3,})', actual)
            stem = re.sub(r'\.\d{3,}$', '', requested)
            verified_suffix = collision and suffix_match is not None and stem.startswith(suffix_match.group(1))
            if len(actual.encode('utf-8')) > self.maximum_bytes or (actual != requested and (shortened or not verified_suffix)):
                raise self.error(key, 'Requested %r but Blender assigned %r (collision=%s)'
                                 % (requested, actual, collision))
            block[METADATA] = key_json(key)
            self.entries[key] = block
            if self._import_cache is not None:
                self._import_cache['trusted'][key] = block
                self._names(key[1]).add(actual)
            for transaction in self.transactions:
                transaction.append(key)
            return block
        except Exception:
            if block is not None:
                collection.remove(block, do_unlink=True)
            raise
        finally:
            self.release(key)

    def copy(self, key, template):
        def factory(name):
            block = template.copy()
            block.name = name
            return block
        return self.create(key, factory)

    def remove(self, block):
        if block is None:
            return
        try:
            key = self.identity(block)
        except ReferenceError:
            return
        if key is None or self.resolve(key) != block:
            raise MappingError('Refusing to delete an unregistered data-block %r' % block.name)
        name = block.name
        getattr(self.bpy.data, key[1]).remove(block, do_unlink=True)
        if self._import_cache is not None:
            self._import_cache['trusted'].pop(key, None)
            self._names(key[1]).discard(name)
        self.entries.pop(key, None)
        self.release(key)

    @contextmanager
    def transaction(self):
        created = []
        previous = set(self.reservations)
        self.transactions.append(created)
        try:
            yield
        except Exception:
            # Objects before their geometry; materials before their actions.
            order = {name: i for i, name in enumerate(NAMESPACES)}
            for key in sorted(created, key=lambda k: order[k[1]]):
                block = self.resolve(key)
                if block is not None:
                    self.remove(block)
            raise
        finally:
            self.transactions.pop()
            for key in set(self.reservations) - previous:
                self.release(key)


_registry = None


def get_registry():
    global _registry
    if _registry is None:
        _registry = NameRegistry()
        from bpy.app.handlers import load_post, persistent
        if _reset_registry not in load_post:
            load_post.insert(0, persistent(_reset_registry))
    return _registry


def _reset_registry(_):
    global _registry
    _registry = None
