
import datetime
import zodbpickle


class Py3Datetime(datetime.datetime):

    def __reduce__(self):
        type_info, args = super(Py3Datetime, self).__reduce__()
        assert len(args) == 1
        return (datetime.datetime, (zodbpickle.binary(args[0]),))

    def __reduce_ex__(self, protocol):
        type_info, args = super(Py3Datetime, self).__reduce_ex__(protocol)
        assert len(args) == 1
        return (datetime.datetime, (zodbpickle.binary(args[0]),))


class Py3Date(datetime.date):

    def __reduce__(self):
        type_info, args = super(Py3Date, self).__reduce__()
        assert len(args) == 1
        return (datetime.date, (zodbpickle.binary(args[0]),))

    def __reduce_ex__(self, protocol):
        type_info, args = super(Py3Date, self).__reduce_ex__(protocol)
        assert len(args) == 1
        return (datetime.date, (zodbpickle.binary(args[0]),))


class Py3Time(datetime.time):

    def __reduce__(self):
        type_info, args = super(Py3Time, self).__reduce__()
        assert len(args) == 1
        return (datetime.time, (zodbpickle.binary(args[0]),))

    def __reduce_ex__(self, protocol):
        type_info, args = super(Py3Time, self).__reduce_ex__(protocol)
        assert len(args) == 1
        return (datetime.time, (zodbpickle.binary(args[0]),))


CONVERT_RENAMES = {
    'datetime datetime': 'zodbupdate.convert Py3Datetime',
    'datetime date': 'zodbupdate.convert Py3Date',
    'datetime time': 'zodbupdate.convert Py3Time'}
