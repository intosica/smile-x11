app_id = 'local.winpanel.Smile'
desktop_dir = join_paths(get_option('datadir'), 'applications')

desktop_file = configure_file(
  input: app_id + '.desktop.in', output: app_id + '.desktop',
  copy: true, install: true, install_dir: desktop_dir)

install_data(configure_file(
  input: app_id + '.autostart.desktop.in', output: app_id + '.autostart.desktop', copy: true),
  install_dir: join_paths(get_option('sysconfdir'), 'xdg', 'autostart'),
  rename: app_id + '.desktop')

# D-Bus activation: first `smile-panel --toggle` (or any activation) starts the resident instance
conf_svc = configuration_data()
conf_svc.set('bindir', join_paths(get_option('prefix'), get_option('bindir')))
configure_file(
  input: app_id + '.service.in', output: app_id + '.service',
  configuration: conf_svc, install: true,
  install_dir: join_paths(get_option('datadir'), 'dbus-1', 'services'))

configure_file(
  input: app_id + '.metainfo.xml.in', output: app_id + '.metainfo.xml',
  copy: true, install: true,
  install_dir: join_paths(get_option('datadir'), 'metainfo'))

install_data(app_id + '.gschema.xml',
  install_dir: join_paths(get_option('datadir'), 'glib-2.0/schemas'))

subdir('icons')
subdir('assets')
