from paithon.utils.core import AbstractMethodError


class RecordWriter(object):

    def write_header(self, header):
        raise AbstractMethodError()

    def write_record(self, record):
        raise AbstractMethodError()
