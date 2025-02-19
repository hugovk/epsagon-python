"""
Base Event class
"""

from __future__ import absolute_import
import sys
import time
import inspect
import uuid
from .common import ErrorCode
from .constants import (
    SHOULD_REMOVE_EXCEPTION_FRAMES,
)


class BaseEvent(object):
    """
    Represents base trace's event
    """

    ORIGIN = 'base'
    RESOURCE_TYPE = 'base'

    def __init__(self, start_time):
        """
        Initialize.
        :param start_time: event's start time (epoch)
        """

        self.start_time = start_time
        self.event_id = ''
        self.origin = self.ORIGIN
        self.duration = 0.0
        self.error_code = ErrorCode.OK
        self.exception = {}
        self.terminated = False

        self.resource = {
            'type': self.RESOURCE_TYPE,
            'name': '',
            'operation': '',
            'metadata': {},
        }

        if self.origin == 'runner':
            self.resource['metadata']['trace_id'] = str(uuid.uuid4())

    @staticmethod
    def load_from_dict(event_data):
        """
        Load Event object from dict.
        :param event_data: dict
        :return: Event
        """

        event = BaseEvent(event_data['start_time'])
        event.event_id = event_data['id']
        event.origin = event_data['origin']
        event.duration = event_data['duration']
        event.error_code = event_data['error_code']
        event.resource = event_data['resource']
        if event.error_code == ErrorCode.EXCEPTION:
            event.exception = event_data['exception']

        return event

    def to_dict(self):
        """
        Converts Event to dict.
        :return: dict
        """

        self_as_dict = {
            'id': self.event_id,
            'start_time': self.start_time,
            'duration': self.duration,
            'origin': self.origin,
            'error_code': self.error_code,
            'resource': self.resource,
        }

        if self.error_code == ErrorCode.EXCEPTION:
            self_as_dict['exception'] = self.exception

        return self_as_dict

    def terminate(self):
        """
        Sets duration time.
        :return: None
        """
        if not self.terminated:
            self.duration = time.time() - self.start_time
            self.terminated = True

    def set_error(self):
        """
        Sets general error.
        :return: None
        """
        if self.error_code != ErrorCode.EXCEPTION:
            self.error_code = ErrorCode.ERROR

    def _copy_user_data_safely(self, data):
        # pylint: disable=no-self-use
        """
        Safely copies user data in order to be able to send it in the trace.
        Converts any tuple keys to str (required for json.dumps).
        """
        if not data or not isinstance(data, (list, tuple, dict)):
            return data

        if isinstance(data, (list, tuple)):
            return [
                self._copy_user_data_safely(item) for item in data
            ]

        # data is a dict
        copied_dict = data.copy()
        for key in data:
            value = self._copy_user_data_safely(data[key])
            if key is None or not isinstance(key, (
                    str,
                    int,
                    float,
                    bool,
            )): # the only supported keys
                copied_dict.pop(key)
                copied_dict[str(key)] = value

        return copied_dict

    def set_exception(
            self,
            exception,
            traceback_data,
            handled=True,
            from_logs=False
    ):
        """
        Sets exception data on event.
        :param exception: Exception object
        :param traceback_data: traceback string
        :param handled: False if the exception was raised from the wrapped
            function
        :param from_logs: True if the exception was captured from logging
        """
        self.error_code = ErrorCode.EXCEPTION
        if hasattr(type(exception), '__name__'):
            self.exception['type'] = type(exception).__name__
        else:
            self.exception['type'] = 'Unknown'
        self.exception['message'] = str(exception)
        self.exception['traceback'] = self._copy_user_data_safely(
            traceback_data
        )
        self.exception['time'] = time.time()
        # Check if to collect the frames
        # Adding python frames (input data of functions in stack) in python 3.
        # Ignoring filenames with /epsagon since they are ours.
        if not SHOULD_REMOVE_EXCEPTION_FRAMES:
            if sys.version_info.major == 3:
                self.exception['frames'] = {
                    '/'.join([
                        frame.filename,
                        frame.function,
                        str(frame.lineno)
                    ]): frame.frame.f_locals
                    for frame in inspect.trace()
                    if '/epsagon' not in frame.filename and frame.frame.f_locals
                }
        self.exception.setdefault('additional_data', {})['handled'] = handled
        if from_logs:
            self.exception['additional_data']['from_logs'] = True
