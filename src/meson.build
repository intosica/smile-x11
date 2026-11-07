pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'smile_panel')

gnome.compile_resources('smile-panel',
  'smile.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

# GTK4/GObject/python-xlib only exist for the *system* python; a conda/venv
# python3 earlier in PATH would produce a launcher that cannot import gi.
# Override with: meson setup build -Dpython_path=/usr/bin/python3
py = import('python').find_installation(get_option('python_path') != '' ? get_option('python_path') : '/usr/bin/python3')

conf = configuration_data()
conf.set('PYTHON', py.full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'smile-panel.in',
  output: 'smile-panel',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

install_subdir('.', install_dir: moduledir, exclude_files: ['meson.build', 'smile-panel.in', 'smile.gresource.xml'])
