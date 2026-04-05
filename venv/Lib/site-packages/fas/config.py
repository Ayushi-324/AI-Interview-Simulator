import os
import sys
import yaml
import tempfile

# py2/py3 compatibility
if sys.version_info[0] == 2:
    def iteritems(d):
        return d.iteritems()
else:
    def iteritems(d):
        return d.items()


class Config(object):
    def __init__(self, file_path):
        self._file_path = file_path
        if not os.path.isfile(self._file_path):
            with open(self._file_path, "w") as conf:
                data = {'faaspot': {'profile': '', 'profiles': {}}}
                yaml.dump(data, conf, default_flow_style=False)
        with open(self._file_path, "r") as conf:
            config_data = yaml.load(conf)
            self._dict = udict.fromdict(config_data)

    def __getattr__(self, attr):
        return self._dict.get(attr)

    def save(self, file_path=None):
        fd, temp_file = tempfile.mkstemp()
        os.close(fd)
        with open(temp_file, 'w') as f:
            data = self._dict.todict()
            yaml.dump(data, f, default_flow_style=False)
        file_path = file_path or self._file_path
        os.rename(temp_file, file_path)
        self._dict = udict.fromdict(data)


# For internal use only as a value that can be used as a default
# and should never exist in a dict.
_MISSING = object()


class udict(dict):

    """
    A dict that supports attribute-style access and hierarchical keys.
    See `__getitem__` for details of how hierarchical keys are handled,
    and `__getattr__` for details on attribute-style access.
    Subclasses may define a '__missing__' method (must be an instance method
    defined on the class and not just an instance variable) that accepts one
    parameter. If such a method is defined, then a call to `my_udict[key]`
    (or the equivalent `my_udict.__getitem__(key)`) that fails will call
    the '__missing__' method with the key as the parameter and return the
    result of that call (or raise any exception the call raises).
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize a new `udict` using `dict.__init__`.
        When passing in a dict arg, this won't do any special
        handling of values that are dicts. They will remain plain dicts inside
        the `udict`. For a recursive init that will convert all
        dict values in a dict to udicts, use `udict.fromdict`.
        Likewise, dotted keys will not be treated specially, so something
        like `udict({'a.b': 'a.b'})` is equivalent to `ud = udict()` followed
        by `setattr(ud, 'a.b', 'a.b')`.
        """
        dict.__init__(self, *args, **kwargs)

    def __getitem__(self, key):
        """
        Get mapped value for given `key`, or raise `KeyError` if no such
        mapping.
        The `key` may be any value that is valid for a plain `dict`. If the
        `key` is a dotted key (a string like 'a.b' containing one or more
        '.' characters), then the key will be split on '.' and interpreted
        as a sequence of `__getitem__` calls. For example,
        `d.__getitem__('a.b')` would be interpreted as (approximately)
        `d.__getitem__('a').__getitem__('b')`. If the key is not a dotted
        it is treated normally.
        :exceptions:
        - KeyError: if there is no such key on a dict (or object that supports
          `__getitem__`) at any level of the dotted-key traversal.
        - TypeError: if key is not hashable or if an object at some point
          in the dotted-key traversal does not support `__getitem__`.
        """
        if not isinstance(key, str) or '.' not in key:
            return dict.__getitem__(self, key)
        try:
            obj, token = _descend(self, key)
            return _get(obj, token)
        except KeyError:
            # if '__missing__' is defined on the class, then we can delegate
            # to that, but we don't delegate otherwise for consistency with
            # plain 'dict' behavior, which requires '__missing__' to be an
            # instance method and not just an instance variable.
            if hasattr(type(self), '__missing__'):
                return self.__missing__(key)
            raise

    def __setitem__(self, key, value):
        """
        Set `value` for given `key`.
        See `__getitem__` for details of how `key` is intepreted if it is a
        dotted key and for exceptions that may be raised.
        """
        if not isinstance(key, str) or '.' not in key:
            return dict.__setitem__(self, key, value)

        obj, token = _descend(self, key)
        return dict.__setitem__(obj, token, value)

    def __delitem__(self, key):
        """
        Remove mapping for `key` in self.
        See `__getitem__` for details of how `key` is intepreted if it is a
        dotted key and for exceptions that may be raised.
        """
        if not isinstance(key, str) or '.' not in key:
            dict.__delitem__(self, key)
            return
        obj, token = _descend(self, key)
        del obj[token]

    def __getattr__(self, key):
        try:
            # no special treatement for dotted keys, but we need to use
            # 'get' rather than '__getitem__' in order to avoid using
            # '__missing__' if key is not in dict
            val = dict.get(self, key, _MISSING)
            if val is _MISSING:
                raise AttributeError("no attribute '%s'" % (key,))
            return val
        except KeyError as e:
            raise AttributeError("no attribute '%s'" % (e.args[0],))

    def __setattr__(self, key, value):
        # normal setattr behavior, except we put it in the dict
        # instead of setting an attribute (i.e., dotted keys are
        # treated as plain keys)
        dict.__setitem__(self, key, value)

    def __delattr__(self, key):
        try:
            # no special handling of dotted keys
            dict.__delitem__(self, key)
        except KeyError as e:
            raise AttributeError("no attribute '%s'" % (e.args[0]))

    def __reduce__(self):
        # pickle the contents of a udict as a list of items;
        # __getstate__ and __setstate__ aren't needed
        constructor = self.__class__
        instance_args = (list(iteritems(self)),)
        return constructor, instance_args

    def get(self, key, default=None):
        # We can't use self[key] to support `get` here, because a missing key
        # should return the `default` and should not use a `__missing__`
        # method if one is defined (as happens for self[key]).
        if not isinstance(key, str) or '.' not in key:
            return dict.get(self, key, default)
        try:
            obj, token = _descend(self, key)
            return _get(obj, token)
        except KeyError:
            return default

    @classmethod
    def fromkeys(self, seq, value=None):
        return udict((elem, value) for elem in seq)

    @classmethod
    def fromdict(cls, mapping):
        """
        Create a new `udict` from the given `mapping` dict.
        The resulting `udict` will be equivalent to the input
        `mapping` dict but with all dict instances (recursively)
        converted to an `udict` instance.  If you don't want
        this behavior (i.e., you want sub-dicts to remain plain dicts),
        use `udict(mapping)` instead.
        """
        ud = cls()
        for k in mapping:
            v = dict.__getitem__(mapping, k)  # okay for py2/py3
            if isinstance(v, dict):
                v = cls.fromdict(v)
            dict.__setitem__(ud, k, v)
        return ud

    def todict(self):
        """
        Create a plain `dict` from this `udict`.
        The resulting `dict` will be equivalent to this `udict`
        but with every `udict` value (recursively) converted to
        a plain `dict` instance.
        """
        d = dict()
        for k in self:
            v = dict.__getitem__(self, k)
            if isinstance(v, udict):
                v = v.todict()
            d[k] = v
        return d

    def copy(self):
        """
        Return a shallow copy of this `udict`.
        For a deep copy, use `udict.fromdict` (as long as there aren't
        plain dict values that you don't want converted to `udict`).
        """
        return udict(self)

    def setdefault(self, key, default=None):
        """
        If `key` is in the dictionary, return its value.
        If not, insert `key` with a value of `default` and return `default`,
        which defaults to `None`.
        """
        val = self.get(key, _MISSING)
        if val is _MISSING:
            val = default
            self[key] = default
        return val

    def __contains__(self, key):
        return self.get(key, _MISSING) is not _MISSING

    def pop(self, key, *args):
        if not isinstance(key, str) or '.' not in key:
            return dict.pop(self, key, *args)
        try:
            obj, token = _descend(self, key)
        except KeyError:
            if args:
                return args[0]
            raise
        else:
            return dict.pop(obj, token, *args)

    def __dir__(self):
        """
        Expose the expected instance and class attributes and methods
        for the builtin `dir` method, as well as the top-level keys that
        are stored.
        """
        return sorted(set(dir(udict)) | set(self.keys()))


# helper to do careful and consistent `obj[name]`
def _get(obj, name):
    """
    Get the indexable value with given `name` from `obj`, which may be
    a `dict` (or subclass) or a non-dict that has a `__getitem__` method.
    """
    try:
        # try to get value using dict's __getitem__ descriptor first
        return dict.__getitem__(obj, name)
    except TypeError:
        # if it's a dict, then preserve the TypeError
        if isinstance(obj, dict):
            raise
        # otherwise try one last time, relying on __getitem__ if any
        return obj[name]


# helper for common use case of traversing a path like 'a.b.c.d'
# to get the 'a.b.c' object and do something to it with the 'd' token
def _descend(obj, key):
    """
    Descend on `obj` by splitting `key` on '.' (`key` must contain at least
    one '.') and using `get` on each token that results from splitting
    to fetch the successive child elements, stopping on the next-to-last.
     A `__getitem__` would do `dict.__getitem__(value, token)` with the
     result, and a `__setitem__` would do `dict.__setitem__(value, token, v)`.
    :returns:
    (value, token) - `value` is the next-to-last object found, and
    `token` is the last token in the `key` (the only one that wasn't consumed
    yet).
    """
    tokens = key.split('.')
    assert len(tokens) > 1
    value = obj
    for token in tokens[:-1]:
        value = _get(value, token)
    return value, tokens[-1]