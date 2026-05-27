-- ============================================================
-- s_exp_datos_iniciales.sql
-- Datos mínimos necesarios para que el módulo Solicitud de Expedientes
-- funcione en una BD recién migrada (catálogos + ubicación ARCHIVO).
--
-- NO incluye datos de usuarios/RRHH/personal — eso se configura aparte
-- desde el módulo correspondiente.
--
-- USO:
--   mysql -u <usuario> -p <nombre_base> < s_exp_datos_iniciales.sql
-- ============================================================

-- ------------------------------------------------------------
-- 1. Estados del flujo de solicitud (s_exp_estadosolicitud)
-- ------------------------------------------------------------
INSERT IGNORE INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES
('SOL_PENDIENTE',            'Pendiente',                    'Esperando aprobación del admin'),
('SOL_APROBADA_ORGANIZANDO', 'Buscando expedientes',         'Aprobada, admin busca expedientes en archivo'),
('SOL_LISTO_RECOGER',        'Listo para recoger',           'Listos, usuario debe pasar a retirar'),
('SOL_EN_PRESTAMO',          'En prestamo',                  'Entregada al usuario, cronómetro activo'),
('SOL_EN_DEVOLUCION',        'En devolucion / Por revisar',  'Usuario marcó para devolver'),
('SOL_INCOMPLETA',           'Devolucion incompleta',        'Devolución parcial, faltan expedientes'),
('SOL_FINALIZADA',           'Finalizada',                   'Devolución completa cerrada'),
('SOL_RECHAZADA',            'Rechazada',                    'No se aprobó la solicitud');


-- ------------------------------------------------------------
-- 2. Estados físicos del expediente (s_exp_estadoexpedientefisico)
-- ------------------------------------------------------------
INSERT IGNORE INTO s_exp_estadoexpedientefisico (codigo, nombre) VALUES
('EXP_DISPONIBLE', 'Disponible'),
('EXP_APARTADO',   'Apartado en solicitud'),
('EXP_PRESTADO',   'En prestamo'),
('EXP_PERDIDO',    'Perdido'),
('EXP_BAJA',       'Retirado / Dado de baja');


-- ------------------------------------------------------------
-- 3. Motivos de solicitud reales del hospital (s_exp_motivosolicitud)
-- ------------------------------------------------------------
INSERT IGNORE INTO s_exp_motivosolicitud (nombre, activo) VALUES
('ANALISIS',                            1),
('COMISION QUIRURGICA',                 1),
('COMPLICACIONES NEONATALES',           1),
('COMPLICACIONES OBSTETRICAS',          1),
('CONSTANCIA',                          1),
('DEFUNCIONES',                         1),
('FICHAS',                              1),
('INFECCIONES',                         1),
('INVESTIGACION',                       1),
('MEDICION',                            1),
('MONITORIA',                           1),
('REPOSICION DE CONSTANCIA NACIMIENTO', 1),
('REVISION',                            1),
('REVISION REFERENCIAS',                1),
('REVISION SAI',                        1),
('TESIS',                               1);


-- ------------------------------------------------------------
-- 4. Localizacion 'ARCHIVO' (donde regresan los expedientes devueltos)
--    NOTA: pertenece al módulo expediente, pero el módulo s_exp la necesita
--    para que el flujo de devolución funcione.
-- ------------------------------------------------------------
INSERT IGNORE INTO expediente_localizacion (descripcion_localizacion, estado)
VALUES ('ARCHIVO', 1);


-- ============================================================
-- FIN — Datos iniciales del módulo s_exp insertados.
-- ============================================================
