project('smile-panel',
    version: '3.0.0',
    meson_version: '>= 0.59.0',
    default_options: [ 'warning_level=2', ],
)

i18n = import('i18n')
gnome = import('gnome')

subdir('data')
subdir('src')
subdir('po')

gnome.post_install(
  glib_compile_schemas: true,
  update_desktop_database: true,
)
