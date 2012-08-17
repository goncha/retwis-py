#!/usr/bin/env python
# -*- coding: utf-8 -*-


# Chdir into this module file's directory
import os
module_dir = os.path.dirname(__file__)
if module_dir:
  os.chdir(module_dir)


import web

# Webpy config
web.config.debug = True


# Webpy app instance
app = web.auto_application()


# Redis
import redis
redis_pool = redis.ConnectionPool(host='localhost', port=6379, db=0)


# Webpy session
from web.session import Store

class RedisStore(Store):
  def __init__(self, pool):
    self.pool = pool

  def _redis(self):
    return redis.Redis(connection_pool = self.pool)

  def _rkey(self, key):
    return 'auth:%s' % (key,)

  def __contains__(self, key):
    return self._redis().exists(self._rkey(key))

  def __getitem__(self, key):
    value = self._redis().get(self._rkey(key))
    if value:
      return self.decode(value)
    else:
      raise KeyError, key

  def __setitem__(self, key, value):
    rkey = self._rkey(key)
    r = self._redis()
    r.set(rkey, self.encode(value))
    r.expire(rkey, web.config.session_parameters.timeout)

  def __delitem__(self, key):
    self._redis().delete(self._rkey(key))

  def cleanup(self, timeout):
    pass



if not web.config.get('_session'):
  session = web.session.Session(app,
                                RedisStore(redis_pool))
  web.config._session = session
else:
  session = web.config._session


# Webpy templates
render = web.template.render('templates/',
                             base='layout',
                             globals={'context': session})


# utilities
def see_other_url(path):
  return web.ctx.home + web.http.url(path)


def logged_in():
  uid = session.get('account')
  return uid and redis.Redis(connection_pool=redis_pool).get('uid:%s:username'%(uid,))


def require_auth(fn):
  def new_func(*args, **kws):
    if logged_in():
      return fn(*args, **kws)
    else:
      raise web.seeother(see_other_url('/login'))
  return new_func



#################
# Webpy Pages
#################
class index(app.page):
  path='^/(?:index)?$'

  def GET(self):
    if logged_in():
      raise web.seeother(see_other_url('/home'))
    else:
      return render.welcome()

class register(app.page):
  def POST(self):
    i = web.input()
    username = i.get('username')
    password = i.get('password')
    password2 = i.get('password2')

    if username and password and password2:
      r = redis.Redis(connection_pool=redis_pool)
      rkey = 'username:%s:uid'%(username,)
      if r.exists(rkey):
        return render.welcome(register_msg='Username `%s\' exists'%(username,))

      if password == password2:
        uid = r.incr('global:nextUserId')
        if 1 == r.setnx(rkey, uid):
          r.set('uid:%d:username'%(uid,), username)
          r.set('uid:%d:password'%(uid,), password)
          session['account'] = uid
          raise web.seeother(see_other_url('/home'))
        else:
          return render.welcome(register_msg='Username `%s\' exists'%(username,))
      else:
        return render.welcome(register_msg='Passwords not matched')
    else:
      return render.welcome(register_msg='Empty username or passwords')


class login(app.page):
  def POST(self):
    i = web.input()
    username = i.get('username')
    password = i.get('password')

    if username and password:
      r = redis.Redis(connection_pool=redis_pool)
      uid = r.get('username:%s:uid'%(username,))
      if uid and password == r.get('uid:%s:password'%(uid,)):
        session['account'] = uid
        raise web.seeother(see_other_url('/home'))
      else:
        return render.welcome(login_msg='Username `%s\' does not exist, or wrong password'%(username,))
    else:
      return render.welcome(login_msg='Empty username or passwords')


@require_auth
class logout(app.page):
  def GET(self):
    session.kill()
    raise web.seeother(see_other_url('/'))


@require_auth
class home(app.page):
  def GET(self):
    return render.home()





if __name__ == '__main__':
  app.run()



# Local Variables: **
# comment-column: 56 **
# indent-tabs-mode: nil **
# python-indent: 2 **
# End: **
