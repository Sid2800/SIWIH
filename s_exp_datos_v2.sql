-- Script de insercion datos ESTATICOS s_exp v2 (FUNCIONAL)
-- Ejecutar en MySQL Workbench: Copiar TODO, pegar en SQL, ejecutar
-- O CMD: mysql -u root -p siwi < s_exp_datos_v2.sql

SET FOREIGN_KEY_CHECKS = 0;

-- ===== LIMPIAR TABLA MotivoSolicitud =====
TRUNCATE TABLE s_exp_motivosolicitud;

-- ===== INSERTAR Motivos =====
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (1, 'ANALISIS', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (2, 'COMISION QUIRURGICA', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (3, 'COMPLICACIONES NEONATALES', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (4, 'COMPLICACIONES OBSTETRICAS', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (5, 'CONSTANCIA', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (6, 'DEFUNCIONES', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (7, 'FICHAS', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (8, 'INFECCIONES', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (9, 'INVESTIGACION', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (10, 'MEDICION', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (11, 'MONITORIA', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (12, 'REPOSICION DE CONSTANCIA NACIMIENTO', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (13, 'REVISION', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (14, 'REVISION REFERENCIAS', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (15, 'REVISION SAI', 1);
INSERT INTO s_exp_motivosolicitud (id, nombre, activo) VALUES (16, 'TESIS', 1);

-- ===== LIMPIAR TABLA EstadoSolicitud =====
DELETE FROM s_exp_estadosolicitud WHERE codigo LIKE 'SOL_%';

-- ===== INSERTAR Estados Solicitud =====
INSERT INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES ('SOL_APROBADA_ORGANIZANDO', 'En proceso de organizacion', 'Aprobada, buscando expedientes fisicos.');
INSERT INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES ('SOL_EN_DEVOLUCION', 'En devolucion / Por revisar', 'Personal ha retornado los expedientes.');
INSERT INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES ('SOL_EN_PRESTAMO', 'En prestamo', 'Expedientes entregados al personal.');
INSERT INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES ('SOL_FINALIZADA', 'Finalizada', 'Todos los expedientes devueltos correctamente.');
INSERT INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES ('SOL_INCOMPLETA', 'Devolucion incompleta', 'Faltan expedientes por entregar.');
INSERT INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES ('SOL_LISTO_RECOGER', 'Listo para recoger', 'Expedientes listos en ventanilla.');
INSERT INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES ('SOL_PENDIENTE', 'Pendiente', 'Solicitud creada por el personal.');
INSERT INTO s_exp_estadosolicitud (codigo, nombre, descripcion) VALUES ('SOL_RECHAZADA', 'Rechazada', 'Solicitud rechazada por el administrador.');

-- ===== LIMPIAR TABLA EstadoExpedienteFisico =====
DELETE FROM s_exp_estadoexpedientefisico WHERE codigo LIKE 'EXP_%';

-- ===== INSERTAR Estados Expediente Fisico =====
INSERT INTO s_exp_estadoexpedientefisico (codigo, nombre) VALUES ('EXP_APARTADO', 'Apartado en solicitud');
INSERT INTO s_exp_estadoexpedientefisico (codigo, nombre) VALUES ('EXP_BAJA', 'Retirado / Dado de baja');
INSERT INTO s_exp_estadoexpedientefisico (codigo, nombre) VALUES ('EXP_DISPONIBLE', 'Disponible');
INSERT INTO s_exp_estadoexpedientefisico (codigo, nombre) VALUES ('EXP_PERDIDO', 'Perdido');
INSERT INTO s_exp_estadoexpedientefisico (codigo, nombre) VALUES ('EXP_PRESTADO', 'En prestamo');

-- ===== VERIFICAR INSERCIONES =====
SELECT COUNT(*) as total_motivos FROM s_exp_motivosolicitud;
SELECT COUNT(*) as total_estados_solicitud FROM s_exp_estadosolicitud;
SELECT COUNT(*) as total_estados_expediente FROM s_exp_estadoexpedientefisico;

SET FOREIGN_KEY_CHECKS = 1;
-- Script completado exitosamente. Si ves 16, 8, 5 arriba = datos insertados correctamente.
