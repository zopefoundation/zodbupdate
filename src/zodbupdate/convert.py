
import datetime
import zodbpickle


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


CONVERT_RENAMES = {
    'datetime datetime': 'zodbupdate.convert Datetime',
    'datetime date': 'zodbupdate.convert Date',
    'datetime time': 'zodbupdate.convert Time'}
