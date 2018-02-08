import logging
import six
import datetime
import zodbpickle
import pkg_resources


logger = logging.getLogger('zodbupdate')


class Datetime(datetime.datetime):

    def __reduce__(self):
        type_info, args = super(Datetime, self).__reduce__()
        assert len(args) > 0
        return (datetime.datetime, (zodbpickle.binary(args[0]),) + args[1:])

    def __reduce_ex__(self, protocol):
        type_info, args = super(Datetime, self).__reduce_ex__(protocol)
        assert len(args) > 0
        return (datetime.datetime, (zodbpickle.binary(args[0]),) + args[1:])


class Date(datetime.date):

    def __reduce__(self):
        type_info, args = super(Date, self).__reduce__()
        assert len(args) > 0
        return (datetime.date, (zodbpickle.binary(args[0]),) + args[1:])

    def __reduce_ex__(self, protocol):
        type_info, args = super(Date, self).__reduce_ex__(protocol)
        assert len(args) > 0
        return (datetime.date, (zodbpickle.binary(args[0]),) + args[1:])


class Time(datetime.time):

    def __reduce__(self):
        type_info, args = super(Time, self).__reduce__()
        assert len(args) > 0
        return (datetime.time, (zodbpickle.binary(args[0]),) + args[1:])

    def __reduce_ex__(self, protocol):
        type_info, args = super(Time, self).__reduce_ex__(protocol)
        assert len(args) > 0
        return (datetime.time, (zodbpickle.binary(args[0]),) + args[1:])


def default_renames():
    return {
        ('copy_reg', '_reconstructor'): ('copyreg', '_reconstructor'),
        ('datetime', 'datetime'): ('zodbupdate.convert', 'Datetime'),
        ('datetime', 'date'): ('zodbupdate.convert', 'Date'),
        ('datetime', 'time'): ('zodbupdate.convert', 'Time')}


def decode_attribute(attribute, encoding):

    def decode(data):
        value = data.get(attribute)
        if not isinstance(value, six.text_type):
            data[attribute] = value.decode(encoding)
            return True
        return False

    return decode


def encode_binary(attribute):

    def encode(data):
        value = data.get(attribute)
        if not isinstance(value, zodbpickle.binary):
            data[attribute] = zodbpickle.binary(value)
            return True
        return False

    return encode


def load_decoders():
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
                    decode_attribute(attribute, encoding))
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
            data_fs.write('FS30')
