import appdaemon.conf as conf
import datetime
from datetime import timezone
import time
import uuid
import re
import requests

import appdaemon.homeassistant as ha

class AppDaemon():

#
# Internal
#

  def __init__(self, name, logger, error, args, global_vars):
    self.name = name
    self._logger = logger
    self._error = error
    self.args = args
    self.global_vars = global_vars
    self.config = conf.config
    
  def _check_entity(self, entity):
    if "." not in entity:
      raise ValueError("{}: Invalid entity ID: {}".format(self.name, entity))
    if entity not in conf.ha_state:
      ha.log(conf.logger, "WARNING", "{}: Entity {} not found in Home Assistant".format(self.name, entity))

  def _check_service(self, service):
    if service.find("/") == -1:
      raise ValueError("Invalid Service Name: {}".format(service))  

#
# Utility
#      
 
  def split_entity(self, entity_id):
    self._check_entity(entity_id)
    return(entity_id.split("."))
    
  def split_device_list(self, list):
    return list.split(",")

  def log(self, msg, level = "INFO"):
    ha.log(self._logger, level, msg, self.name)

  def error(self, msg, level = "WARNING"):
    ha.log(self._error, level, msg, self.name)

  def get_app(self, name):
    return conf.objects[name]["object"]
    
  def friendly_name(self, entity_id):
    self._check_entity(entity_id)
    if entity_id in conf.ha_state:
      if "friendly_name" in conf.ha_state[entity_id]["attributes"]:
        return conf.ha_state[entity_id]["attributes"]["friendly_name"]
      else:
        return entity_id
    return None

#
# Device Trackers
#
    
  def get_trackers(self):
    return (key for key, value in self.get_state("device_tracker").items())
    
  def get_tracker_state(self, entity_id):
    self._check_entity(entity_id)
    return(self.get_state(entity_id))
    
  def anyone_home(self):
    return ha.anyone_home()

  def everyone_home(self):
    return ha.everyone_home()   
    
  def noone_home(self):
    return ha.noone_home()
       
#
# State
#
       
  def get_state(self, entity_id = None, attribute = None):
    ha.log(conf.logger, "DEBUG", "get_state: {}.{}".format(entity_id, attribute))
    device = None
    entity = None
    if entity_id != None:
      if "." not in entity_id:
        if attribute != None:
          raise ValueError("{}: Invalid entity ID: {}".format(self.name, entity))
        device = entity_id
        entity = None
      else:
        device, entity = entity_id.split(".")
    if device == None:
      return conf.ha_state
    elif entity == None:
      devices = {}
      for entity_id in conf.ha_state.keys():
        thisdevice, thisentity = entity_id.split(".")
        if device == thisdevice:
          devices[entity_id] = conf.ha_state[entity_id]
      return devices
    elif attribute == None:
      entity_id = "{}.{}".format(device, entity)
      if entity_id in conf.ha_state:
        return conf.ha_state[entity_id]["state"]
      else:
        return None
    else:
      entity_id = "{}.{}".format(device, entity)
      if attribute == "all":
        if entity_id in conf.ha_state:
          return conf.ha_state[entity_id]
        else:
          return None
      else:
        if attribute in conf.ha_state[entity_id]:
          return conf.ha_state[entity_id][attribute]
        elif attribute in conf.ha_state[entity_id]["attributes"]:
            return conf.ha_state[entity_id]["attributes"][attribute]
        else:
          return None

  def set_state(self, entity_id, **kwargs):
    self._check_entity(entity_id)
    ha.log(conf.logger, "DEBUG", "set_state: {}, {}".format(entity_id, kwargs))
    if conf.ha_key != "":
      headers = {'x-ha-access': conf.ha_key}
    else:
      headers = {}
    apiurl = "{}/api/states/{}".format(conf.ha_url, entity_id)
    r = requests.post(apiurl, headers=headers, json=kwargs)
    r.raise_for_status()
    # Update our local copy of state if necessary
    state = r.json()
    conf.ha_state[entity_id] = state
    return state

  def listen_state(self, function, entity = None, **kwargs):
    name = self.name
    if entity != None and "." in entity:
      self._check_entity(entity)
    if name not in conf.callbacks:
        conf.callbacks[name] = {}
    handle = uuid.uuid4()
    conf.callbacks[name][handle] = {"name": name, "id": conf.objects[name]["id"], "type": "state", "function": function, "entity": entity, "kwargs": kwargs}
    return handle
    
  def cancel_listen_state(self, handle):
    name = self.name
    ha.log(conf.logger, "DEBUG", "Canceling listen_state for {}".format(name))
    if name in conf.callbacks and handle in conf.callbacks[name]:
      del conf.callbacks[name][handle]
    if name in conf.callbacks and conf.callbacks[name] == {}:
      del conf.callbacks[name]
  
  def info_listen_state(self, handle):
    name = self.name
    ha.log(conf.logger, "DEBUG", "Calling info_listen_state for {}".format(name))
    if name in conf.callbacks and handle in conf.callbacks[name]:
      callback = conf.callbacks[name][handle]
      return (callback["entity"], callback["kwargs"].get("attribute", None), ha.sanitize_state_kwargs(callback["kwargs"]))
    else:
      raise ValueError("Invalid handle: {}".format(handle))
#
# Event
#

  def fire_event(self, event, **kwargs):
    ha.log(conf.logger, "DEBUG", "fire_event: {}, {}".format(event, kwargs))
    if conf.ha_key != "":
      headers = {'x-ha-access': conf.ha_key}
    else:
      headers = {}
    apiurl = "{}/api/events/{}".format(conf.ha_url, event)
    r = requests.post(apiurl, headers=headers, json = kwargs)
    r.raise_for_status()
    return r.json()

  def listen_event(self, function, event, **kwargs):
    name = self.name
    if name not in conf.callbacks:
        conf.callbacks[name] = {}
    handle = uuid.uuid4()
    conf.callbacks[name][handle] = {"name": name, "id": conf.objects[name]["id"], "type": "event", "function": function, "event": event, "kwargs": kwargs}
    return handle

  def cancel_listen_event(self, handle):
    name = self.name
    ha.log(conf.logger, "DEBUG", "Canceling listen_event for {}".format(name))
    if name in conf.callbacks and handle in conf.callbacks[name]:
      del conf.callbacks[name][handle]
    if name in conf.callbacks and conf.callbacks[name] == {}:
      del conf.callbacks[name]
  
  def info_listen_event(self, handle):
    name = self.name
    ha.log(conf.logger, "DEBUG", "Calling info_listen_event for {}".format(name))
    if name in conf.callbacks and handle in conf.callbacks[name]:
      callback = conf.callbacks[name][handle]
      return (callback["event"], callback["kwargs"].copy())
    else:
      raise ValueError("Invalid handle: {}".format(handle))
#
# Service
#
   
  def call_service(self, service, **kwargs):
    self._check_service(service)    
    d, s = service.split("/")
    ha.log(conf.logger, "DEBUG", "call_service: {}/{}, {}".format(d, s, kwargs))
    if conf.ha_key != "":
      headers = {'x-ha-access': conf.ha_key}
    else:
      headers = {}
    apiurl = "{}/api/services/{}/{}".format(conf.ha_url, d, s)
    r = requests.post(apiurl, headers=headers, json = kwargs)
    r.raise_for_status()
    return r.json()
    
  def turn_on(self, entity_id, **kwargs):
    self._check_entity(entity_id)
    if kwargs == {}:
      rargs = {"entity_id": entity_id}
    else:
      rargs = kwargs
      rargs["entity_id"] = entity_id
    self.call_service("homeassistant/turn_on", **rargs)
    
  def turn_off(self, entity_id):
    self._check_entity(entity_id)
    self.call_service("homeassistant/turn_off", entity_id = entity_id)

  def toggle(self, entity_id):
    self._check_entity(entity_id)
    self.call_service("homeassistant/toggle", entity_id = entity_id)
  
  def select_value(self, entity_id, value):
    self._check_entity(entity_id)
    rargs = {"entity_id": entity_id, "value": value}
    self.call_service("input_slider/select_value", **rargs)

  def select_option(self, entity_id, option):
    self._check_entity(entity_id)
    rargs = {"entity_id": entity_id, "option": option}
    self.call_service("input_select/select_option", **rargs)
  
  def notify(self, message, title=None):
    args ={}
    args["message"] = message
    if title != None:
      args["title"] = title
    self.call_service("notify/notify", **args)

  def persistent_notification(self, message, title=None, id=None):
    args ={}
    args["message"] = message
    if title != None:
      args["title"] = title
    if id != None:
      args["notification_id"] = id
    self.call_service("persistent_notification/create", **args)

#
# Time
#

  def convert_utc(self, utc):
    return datetime.datetime(*map(int, re.split('[^\d]', utc)[:-1])) + datetime.timedelta(minutes=ha.get_tz_offset())
    
  def sun_up(self):
    return conf.sun["next_rising"] > conf.sun["next_setting"]

  def sun_down(self):
    return conf.sun["next_rising"] < conf.sun["next_setting"]
    
  def sunrise(self):
    return ha.sunrise()

  def sunset(self):
    return ha.sunset()
    
  def parse_time(self, time_str):
    return ha.parse_time(time_str)
  
  def now_is_between(self, start_time_str, end_time_str):
    return ha.now_is_between(start_time_str, end_time_str, self.name)

  def time(self):
    return datetime.datetime.fromtimestamp(conf.now).time()
    
  def datetime(self):
    return datetime.datetime.fromtimestamp(conf.now)

  def date(self):
    return datetime.datetime.fromtimestamp(conf.now).date()
#
# Scheduler
#
        
  def cancel_timer(self, handle):
    name = self.name
    ha.cancel_timer(name, handle)
    
  def info_timer(self, handle):
    name = self.name
    ha.log(conf.logger, "DEBUG", "Calling info_timer for {}".format(name))
    if name in conf.schedule and handle in conf.schedule[name]:
      callback = conf.schedule[name][handle]
      return (datetime.datetime.fromtimestamp(callback["timestamp"]), callback["interval"], ha.sanitize_timer_kwargs(callback["kwargs"]))
    else:
      raise ValueError("Invalid handle: {}".format(handle))

         
  def run_in(self, callback, seconds, **kwargs):
    name = self.name
    ha.log(conf.logger, "DEBUG", "Registering run_in in {} seconds for {}".format(seconds, name))  
    # convert seconds to an int if possible since a common pattern is to pass this through from the config file which is a string
    exec_time = ha.get_now_ts() + int(seconds)
    handle = ha.insert_schedule(name, exec_time, callback, False, None, **kwargs)
    return handle

  def run_once(self, callback, start, **kwargs):
    name = self.name
    now = ha.get_now()
    today = now.date()
    event = datetime.datetime.combine(today, start)
    if event < now:
      one_day = datetime.timedelta(days=1)
      event = event + one_day
    exec_time = event.timestamp()
    handle = ha.insert_schedule(name, exec_time, callback, False, None, **kwargs)
    return handle

  def run_at(self, callback, start, **kwargs):
    name = self.name
    now = ha.get_now()
    if start < now:
      raise ValueError("{}: run_at() Start time must be in the future".format(self.name))
    exec_time = start.timestamp()
    handle = ha.insert_schedule(name, exec_time, callback, False, None, **kwargs)
    return handle

  def run_daily(self, callback, start, **kwargs):
    name = self.name
    now = ha.get_now()
    today = now.date()
    event = datetime.datetime.combine(today, start)
    if event < now:
      event = event + datetime.timedelta(days=1)
    handle = self.run_every(callback, event, 24 * 60 * 60, **kwargs)
    return handle
    
  def run_hourly(self, callback, start, **kwargs):
    name = self.name
    now = ha.get_now()
    if start == None:
      event = now + datetime.timedelta(hours=1)
    else:
      event = now
      event = event.replace(minute = start.minute, second = start.second)
      if event < now:
        event = event + datetime.timedelta(hours=1)    
    handle = self.run_every(callback, event, 60 * 60, **kwargs)
    return handle  

  def run_minutely(self, callback, start, **kwargs):
    name = self.name
    now = ha.get_now()
    if start == None:
      event = now + datetime.timedelta(minutes=1)
    else:
      event = now
      event = event.replace(second = start.second)
      if event < now:
        event = event + datetime.timedelta(minutes=1)
    handle = self.run_every(callback, event, 60, **kwargs)
    return handle  

  def run_every(self, callback, start, interval, **kwargs):
    name = self.name
    now = ha.get_now()
    if start < now:
      raise ValueError("start cannot be in the past")
    ha.log(conf.logger, "DEBUG", "Registering run_every starting {} in {}s intervals for {}".format(start, interval, name))  
    exec_time = start.timestamp()
    handle = ha.insert_schedule(name, exec_time, callback, True, None, interval = interval, **kwargs)
    return handle
 
  def _schedule_sun(self, name, type, callback, **kwargs):
    event = ha.calc_sun(type)
    handle = ha.insert_schedule(name, event, callback, True, type, **kwargs)

 
  def run_at_sunset(self, callback, **kwargs):
    name = self.name
    ha.log(conf.logger, "DEBUG", "Registering run_at_sunset with kwargs = {} for {}".format(kwargs, name))    
    handle = self._schedule_sun(name, "next_setting", callback, **kwargs)
    return handle

  def run_at_sunrise(self, callback, **kwargs):
    name = self.name
    ha.log(conf.logger, "DEBUG", "Registering run_at_sunrise with kwargs = {} for {}".format(kwargs, name))    
    handle = self._schedule_sun(name, "next_rising", callback, **kwargs)
    return handle
