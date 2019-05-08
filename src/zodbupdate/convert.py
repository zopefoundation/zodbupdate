import logging
import six
import datetime
import zodbpickle
import pkg_resources
from zodbupdate import utils


logger = logging.getLogger('zodbupdate')


class Datetime(datetime.datetime):

    def __reduce__(self):
        type_info, args = super(Datetime, self).__reduce__()
        assert len(args) > 0
        return (datetime.datetime, (utils.safe_binary(args[0]),) + args[1:])

    def __reduce_ex__(self, protocol):
        type_info, args = super(Datetime, self).__reduce_ex__(protocol)
        assert len(args) > 0
        return (datetime.datetime, (utils.safe_binary(args[0]),) + args[1:])


class Date(datetime.date):

    def __reduce__(self):
        type_info, args = super(Date, self).__reduce__()
        assert len(args) > 0
        return (datetime.date, (utils.safe_binary(args[0]),) + args[1:])

    def __reduce_ex__(self, protocol):
        type_info, args = super(Date, self).__reduce_ex__(protocol)
        assert len(args) > 0
        return (datetime.date, (utils.safe_binary(args[0]),) + args[1:])


class Time(datetime.time):

    def __reduce__(self):
        type_info, args = super(Time, self).__reduce__()
        assert len(args) > 0
        return (datetime.time, (utils.safe_binary(args[0]),) + args[1:])

    def __reduce_ex__(self, protocol):
        type_info, args = super(Time, self).__reduce_ex__(protocol)
        assert len(args) > 0
        return (datetime.time, (utils.safe_binary(args[0]),) + args[1:])


def default_renames():
    return {
        ('UserDict', 'UserDict'): ('collections', 'UserDict'),
        ('__builtin__', 'set'): ('builtins', 'set'),
        ('datetime', 'datetime'): ('zodbupdate.convert', 'Datetime'),
        ('datetime', 'date'): ('zodbupdate.convert', 'Date'),
        ('datetime', 'time'): ('zodbupdate.convert', 'Time')}


def decode_attribute(attribute, encoding, encoding_fallbacks=[]):

    def decode(data):
        value = data.get(attribute)
        if value is None:
            return False
        if isinstance(value, six.text_type):
            if encoding == utils.ENCODING:
                return False
            value = utils.safe_binary(value)
        try:
            data[attribute] = value.decode(encoding)
        except UnicodeDecodeError:
            for encoding_fallback in encoding_fallbacks:
                try:
                    data[attribute] = value.decode(encoding_fallback)
                except UnicodeDecodeError:
                    continue
                logger.warning(
                    'Encoding fallback to "{fallback_encoding:s}" '
                    'while decoding attribute "{attribute:s}" '
                    'from: \n{value}\nto:\n{data_attribute}'.format(
                        fallback_encoding=encoding_fallback,
                        attribute=attribute,
                        value=value,
                        data_attribute=data[attribute],
                    )
                )
                logger.debug(
                    "Encoding fallback on data:\n{data}".format(data=data)
                )
                return True
            else:
                raise UnicodeDecodeError(
                    'encoding={encoding}, fallback_encodings={fallbacks}'.format(
                        encoding=encoding,
                        fallbacks=encoding_fallbacks,
                    ),
                    value,
                    0,
                    0,
                    'Neither with encoding nor with fallbacks.',
                )
        return True

    return decode


def encode_binary(attribute):

    def encode(data):
        value = data.get(attribute)
        if value is not None and not isinstance(value, zodbpickle.binary):
            data[attribute] = utils.safe_binary(value)
            return True
        return False

    return encode


def load_decoders(encoding_fallbacks=[]):
    decoders = {}
    for entry_point in pkg_resources.iter_entry_points('zodbupdate.decode'):
        definition = entry_point.load()
        for attribute_path, encoding in definition.items():
            module, cls, attribute = attribute_path.split(' ')
            if encoding == 'binary':
                decoders.setdefault((module, cls), []).append(
                    encode_binary(attribute))
            else:
                decoders.setdefault((module, cls), []).append(
                    decode_attribute(attribute, encoding, encoding_fallbacks))
        logger.info('Loaded {} decode rules from {}:{}'.format(
            len(definition), entry_point.module_name, entry_point.name))
    return decoders


def update_magic_data_fs(filename):
    if not filename:
        logger.info("We do not know the database file so "
                    "we do not change the magic marker.")
    else:
        logger.info("Updating magic marker for {}".format(filename))
        with open(filename, 'r+b') as data_fs:
            # Override the magic.
            data_fs.write(b'FS30')
