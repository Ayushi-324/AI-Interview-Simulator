import sys
import time
import logging

utils_logger = logging.getLogger(__name__)


class WaitCompletion:
    def __init__(self, wait=True, interval_sleep=5, logger=None):
        self._wait = wait
        self._interval_sleep = interval_sleep
        self._logger = logger if logger else utils_logger
        self._timeout = 600
        self._end_states = ['success', 'failure', 'completed', 'failed', 'cancelled']

    def _extract_uuid(self, response):
        if isinstance(response, basestring):
            result_arr = response.split(':')
            if len(result_arr) != 2:
                raise Exception('Expected: `Execution id: XXX`, '
                                'Got: {0}'.format(result_arr))
            return result_arr[1].strip()
        elif isinstance(response, dict) and 'uuid' in response:
            return response.get('uuid')
        raise Exception('Bad response format, Got: {0}'.format(response))

    def __call__(self, func):
        def _wait(func_self, *args, **kwargs):
            func_name = func.func_name
            wait = kwargs.get('wait')
            self._wait = wait if 'wait' in kwargs else self._wait
            self._logger.debug('Running: {0}'.format(func_name))
            result = func(func_self, *args, **kwargs)
            if not self._wait:
                return result
            task_id = self._extract_uuid(result)
            self._logger.info('Waiting for completion of task: `{0}`'.format(task_id))
            for i in xrange(600):
                task_status_uri = 'executions/{0}'.format(task_id)
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(self._interval_sleep)
                response = func_self.api.get(uri=task_status_uri)
                self._logger.debug('`{0}` wait for completion. '
                                   'Current status: {1}'.format(func_name, response))
                status = response.get('status')
                if status and status.lower() in self._end_states:
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                    return response['output']
            return 'Timeout waiting for {0} completion'.format(func_name)

        return _wait


class SafeRun:
    def __init__(self, default=None, message=None):
        self._default = default
        self._message = message

    def __call__(self, call):
        def _safeRun(*args, **kwargs):
            try:
                return call(*args, **kwargs)
            except:
                if self._message is not None:
                    try:
                        logging.exception(self._message)
                    except:
                        pass
                return self._default

        return _safeRun


# def error_handled(use_status=False, log=True):
#     def _decorator(f):
#         @wraps(f)
#         def _wrapper(*args, **kwargs):
#             try:
#                 return f(*args, **kwargs)
#             except Exception as e:
#                 if log:
#                     if 'logger' in kwargs:
#                         logger = kwargs['logger']
#                     else:
#                         logger = logging.getLogger(f.__name__)
#                     logger.exception('Exception in {0}(*{1}, **{2})'
#                                      .format(f.__name__, args, kwargs))
#                 raise
#
#         return _wrapper
#
#     return _decorator
