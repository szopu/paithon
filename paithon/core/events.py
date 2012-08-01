from paithon.core.exceptions import AbstractMethodError


class EventListener(object):
    def on_event(self, event, source, params):
        raise AbstractMethodError()


class EventDispatcherMixin(object):
    def __init__(self):
        self._event_listeners = {}

    def add_event_listener(self, event, listener):
        self._event_listeners.setdefault(event, []).append(listener)

    def remove_event_listener(self, event, listener):
        listeners = self._event_listeners.get(event, [])
        try:
            listeners.remove(listener)
        except ValueError:
            raise ValueError('EventDispatcher.remove_listener: listener not on list')

    def trigger_event(self, event, params):
        for listener in self._event_listeners.get(event, []):
            listener.on_event(event, self, params)

    def trigger_ev(self, event, **params):
        self.trigger_event(event, params)