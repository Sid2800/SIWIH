(function () {
	const container = document.querySelector('.th-container');
	if (!container) {
		return;
	}

	const urls = {
		buscarPacientes: container.dataset.urlBuscarPacientes || '',
		buscarEmpleados: container.dataset.urlBuscarEmpleados || '',
		cancelar: container.dataset.urlCancelar || '',
	};
	const isReadOnly = container.dataset.modo === 'ver';
	const tipoPacientesId = String(container.dataset.tipoPacientesId || '');
	const destinosInfo = safeParse(container.dataset.destinosInfo, {});
	const puntosInfo = safeParse(container.dataset.puntosInfo, {});

	const form = document.getElementById('solicitud-form');
	const inputArea = document.getElementById('id_area_solicitante');
	const puntoSelect = document.getElementById('id_punto_solicitud');
	const areaLabel = document.getElementById('th-area-solicitante');
	const tipoSolicitudSelect = document.getElementById('id_tipo_solicitud');
	const destinoSelect = document.getElementById('id_lugar_destino');
	const pacientesInput = document.getElementById('id_pacientes_json');
	const empleadosInput = document.getElementById('id_empleados_json');
	const pacientesResultados = document.getElementById('th-pacientes-resultados');
	const pacientesSeleccionadosTbody = document.getElementById('th-pacientes-seleccionados');
	const empleadosSeleccionadosTbody = document.getElementById('th-empleados-seleccionados');
	const buscarPacienteInput = document.getElementById('th-buscar-paciente');
	const buscarPacienteBtn = document.getElementById('th-btn-buscar-paciente');
	const pacientesSearch = document.getElementById('th-pacientes-search');
	const criterioPaciente = document.getElementById('th-criterio-paciente');
	const limpiarPacienteBtn = document.getElementById('th-btn-limpiar-paciente');
	const criterioEmpleado = document.getElementById('th-criterio-empleado');
	const empleadoSearchSelect = document.getElementById('th-buscar-empleado-select');
	const limpiarEmpleadoBtn = document.getElementById('th-btn-limpiar-empleado');
	const btnCancelar = document.getElementById('th-btn-cancelar-solicitud');

	if (!pacientesInput || !empleadosInput || !pacientesResultados || !pacientesSeleccionadosTbody || !empleadosSeleccionadosTbody) {
		return;
	}

	let pacientesSeleccionados = safeParse(pacientesInput.value, []);
	let empleadosSeleccionados = safeParse(empleadosInput.value, []);
	let empleadoSearchTom = null;
	const empleadosBusquedaMap = {};

	function safeParse(raw, defaultValue) {
		if (!raw) return defaultValue;
		try { return JSON.parse(raw); } catch (_) { return defaultValue; }
	}

	function formatInstitutionText(info) {
		if (!info) {
			return '';
		}
		const parts = [info.nombre || '-'];
		if (info.alias) {
			parts.push('Alias: ' + info.alias);
		}
		parts.push('Nivel: ' + (info.nivel || '-'));
		parts.push('Región: ' + (info.region || '-'));
		return parts.join(' | ');
	}

	function formatPointText(info) {
		if (!info) {
			return '';
		}
		return [info.nombre || '-', info.nombre_corto || '-', info.tipo || '-'].join(' | ');
	}

	function formatEmployeeSearchText(item) {
		return [
			item.nombre || '-',
			'DNI: ' + (item.dni || '-'),
			(item.unidad_corta || '-'),
			(item.unidad || '-'),
		].join(' | ');
	}

	function hydrateSelectText(select, infoMap, formatter) {
		if (!select || !infoMap) {
			return;
		}
		Array.from(select.options).forEach(function (option) {
			if (!option.value) {
				return;
			}
			const info = infoMap[String(option.value)] || null;
			if (info) {
				option.textContent = formatter(info);
			}
		});
	}

	function escapeHtml(value) {
		return String(value || '')
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;')
			.replace(/'/g, '&#39;');
	}

	function esTipoPacientesSeleccionado() {
		if (!tipoSolicitudSelect || !tipoPacientesId) {
			return true;
		}
		return String(tipoSolicitudSelect.value || '') === tipoPacientesId;
	}

	function puedeGestionarPacientes() {
		return !isReadOnly && esTipoPacientesSeleccionado();
	}

	function initTomSelect(selector, placeholder) {
		const node = document.querySelector(selector);
		if (!node || !window.TomSelect) {
			return null;
		}
		if (node.tomselect) {
			return node.tomselect;
		}
		return new TomSelect(selector, {
			valueField: 'value',
			labelField: 'text',
			searchField: ['text'],
			create: false,
			placeholder: placeholder,
			allowEmptyOption: true,
			sortField: [{ field: 'text', direction: 'asc' }],
		});
	}

	hydrateSelectText(destinoSelect, destinosInfo, formatInstitutionText);
	hydrateSelectText(puntoSelect, puntosInfo, formatPointText);

	initTomSelect('#id_punto_solicitud', 'Punto solicitud');
	initTomSelect('#id_tipo_solicitud', 'Tipo solicitud');
	initTomSelect('#id_prioridad', 'Prioridad');
	initTomSelect('#id_lugar_salida', 'Lugar salida');
	initTomSelect('#id_lugar_destino', 'Lugar destino');

	function setButtonLoading(button, isLoading) {
		if (!button) {
			return;
		}
		if (!button.dataset.originalHtml) {
			button.dataset.originalHtml = button.innerHTML;
		}
		button.disabled = isLoading;
		button.classList.toggle('is-loading', isLoading);
		button.innerHTML = isLoading
			? '<i class="bi bi-arrow-repeat"></i> ' + (button.dataset.loadingText || 'Cargando...')
			: button.dataset.originalHtml;
	}

	function setFieldError(control, message) {
		const field = control ? control.closest('.th-field') : null;
		if (!field) {
			return;
		}
		field.classList.add('th-field--error');
		let errorNode = field.querySelector('.th-field-errors--client');
		if (!errorNode) {
			errorNode = document.createElement('div');
			errorNode.className = 'th-field-errors th-field-errors--client';
			field.appendChild(errorNode);
		}
		errorNode.textContent = message || 'Este campo es obligatorio.';
	}

	function clearFieldError(control) {
		const field = control ? control.closest('.th-field') : null;
		if (!field) {
			return;
		}
		const clientError = field.querySelector('.th-field-errors--client');
		if (clientError) {
			clientError.remove();
		}
		if (!field.querySelector('.th-field-errors')) {
			field.classList.remove('th-field--error');
		}
	}

	function focusControl(control) {
		if (!control) {
			return;
		}
		if (control.tomselect) {
			control.tomselect.focus();
			return;
		}
		control.focus();
	}

	function syncAreaSolicitante() {
		if (!puntoSelect || !areaLabel || !inputArea) return;
		const selectedInfo = puntosInfo[String(puntoSelect.value || '')] || null;
		const txt = selectedInfo ? selectedInfo.nombre : '';
		areaLabel.textContent = txt || '';
		inputArea.value = txt || '';
	}

	function syncHiddenInputs() {
		pacientesInput.value = JSON.stringify(pacientesSeleccionados);
		empleadosInput.value = JSON.stringify(empleadosSeleccionados);
	}

	function renderPacientesSeleccionados() {
		if (!pacientesSeleccionados.length) {
			pacientesSeleccionadosTbody.innerHTML = '<tr><td colspan="4">No hay pacientes seleccionados.</td></tr>';
			syncHiddenInputs();
			return;
		}

		pacientesSeleccionadosTbody.innerHTML = pacientesSeleccionados.map(function (p, idx) {
			const accion = puedeGestionarPacientes()
				? '<button type="button" class="th-btn" data-remove-paciente="' + idx + '"><i class="bi bi-dash-circle"></i> Quitar</button>'
				: '<span class="th-subtitle">-</span>';
			return '\n                <tr>\n                    <td>' + escapeHtml(p.nombre || '-') + '</td>\n                    <td>' + escapeHtml(p.expediente || '-') + '</td>\n                    <td>' + escapeHtml(p.ingreso || '-') + '</td>\n                    <td>' + accion + '</td>\n                </tr>';
		}).join('');
		syncHiddenInputs();
	}

	function renderEmpleadosSeleccionados() {
		if (!empleadosSeleccionados.length) {
			empleadosSeleccionadosTbody.innerHTML = '<tr><td colspan="3">No hay personal seleccionado.</td></tr>';
			syncHiddenInputs();
			return;
		}

		empleadosSeleccionadosTbody.innerHTML = empleadosSeleccionados.map(function (e, idx) {
			const accion = isReadOnly
				? '<span class="th-subtitle">-</span>'
				: '<button type="button" class="th-btn" data-remove-empleado="' + idx + '"><i class="bi bi-dash-circle"></i> Quitar</button>';
			return '\n                <tr>\n                    <td>' + escapeHtml(e.nombre || '-') + '</td>\n                    <td>' + escapeHtml(e.cargo || '-') + '</td>\n                    <td>' + accion + '</td>\n                </tr>';
		}).join('');
		syncHiddenInputs();
	}

	function agregarPaciente(item) {
		const exists = pacientesSeleccionados.some(function (p) {
			return String(p.paciente_id || '') === String(item.paciente_id || '') && String(p.ingreso_id || '') === String(item.ingreso_id || '');
		});
		if (exists) return;
		pacientesSeleccionados.push(item);
		renderPacientesSeleccionados();
	}

	function agregarEmpleado(item) {
		const exists = empleadosSeleccionados.some(function (e) {
			return String(e.empleado_id || '') === String(item.empleado_id || '');
		});
		if (exists) return;
		empleadosSeleccionados.push(item);
		renderEmpleadosSeleccionados();
	}

	async function buscarPacientes() {
		if (!puedeGestionarPacientes()) return;
		const q = (buscarPacienteInput.value || '').trim();
		if (q.length < 2 || !urls.buscarPacientes) return;
		setButtonLoading(buscarPacienteBtn, true);
		const tipo = (criterioPaciente && criterioPaciente.value) ? criterioPaciente.value : 'nombre';
		const params = new URLSearchParams();
		params.append('q', q);
		params.append('tipo', tipo);
		try {
			const resp = await fetch(urls.buscarPacientes + '?' + params.toString());
			const payload = await resp.json();
			const rows = payload.data || [];
			if (!rows.length) {
				pacientesResultados.innerHTML = '<tr><td colspan="4">Sin resultados.</td></tr>';
				toastr.info('No se encontraron pacientes con ese criterio.', 'Información');
				return;
			}
			pacientesResultados.innerHTML = rows.map(function (p, idx) {
				return '\n                <tr>\n                    <td>' + escapeHtml(p.nombre || '-') + '</td>\n                    <td>' + escapeHtml(p.expediente || '-') + '</td>\n                    <td>' + escapeHtml(p.ingreso || '-') + '</td>\n                    <td><button type="button" class="th-btn" data-add-paciente="' + idx + '"><i class="bi bi-plus-circle"></i> Agregar</button></td>\n                </tr>';
			}).join('');
			pacientesResultados.querySelectorAll('[data-add-paciente]').forEach(function (btn) {
				btn.addEventListener('click', function () {
					if (!puedeGestionarPacientes()) return;
					agregarPaciente(rows[Number(btn.dataset.addPaciente)]);
				});
			});
		} catch (_) {
			toastr.warning('Ocurrió un problema al buscar pacientes.', 'Aviso');
		} finally {
			setButtonLoading(buscarPacienteBtn, false);
		}
	}

	function initEmpleadoSearchSelect() {
		if (!empleadoSearchSelect || !window.TomSelect || empleadoSearchSelect.tomselect || isReadOnly) {
			return empleadoSearchSelect ? empleadoSearchSelect.tomselect : null;
		}
		empleadoSearchSelect.innerHTML = '<option value="">Buscar empleado</option>';
		return new TomSelect('#th-buscar-empleado-select', {
			valueField: 'value',
			labelField: 'text',
			searchField: ['text'],
			create: false,
			allowEmptyOption: true,
			placeholder: 'Buscar empleado por nombre',
			loadThrottle: 250,
			maxOptions: 10,
			load: function (query, callback) {
				if (!query || query.trim().length < 2 || !urls.buscarEmpleados) {
					callback([]);
					return;
				}
				const tipo = (criterioEmpleado && criterioEmpleado.value) ? criterioEmpleado.value : 'nombre';
				const params = new URLSearchParams();
				params.append('q', query.trim());
				params.append('tipo', tipo);
				fetch(urls.buscarEmpleados + '?' + params.toString())
					.then(function (resp) { return resp.ok ? resp.json() : Promise.reject(); })
					.then(function (payload) {
						const rows = payload.data || [];
						if (!rows.length) {
							toastr.info('No se encontraron empleados con ese criterio.', 'Información');
						}
						rows.forEach(function (row) {
							empleadosBusquedaMap[String(row.empleado_id)] = row;
						});
						callback(rows.map(function (row) {
							return {
								value: String(row.empleado_id),
								text: formatEmployeeSearchText(row),
							};
						}));
					})
					.catch(function () {
						toastr.warning('Ocurrió un problema al buscar empleados.', 'Aviso');
						callback([]);
					});
			},
			onChange: function (value) {
				const item = empleadosBusquedaMap[String(value || '')];
				if (!item) {
					return;
				}
				agregarEmpleado({
					empleado_id: item.empleado_id,
					nombre: item.nombre,
					cargo: item.cargo,
					observacion: '',
				});
				this.clear(true);
				this.clearOptions();
			},
		});
	}

	function updateEmpleadoSearchPlaceholder(texto) {
		if (!empleadoSearchTom) {
			return;
		}
		empleadoSearchTom.settings.placeholder = texto;
		if (empleadoSearchTom.control_input) {
			empleadoSearchTom.control_input.placeholder = texto;
		}
	}

	function validarFormularioAntesDeEnviar(event) {
		if (!form || isReadOnly) {
			return;
		}
		const controles = Array.from(form.querySelectorAll('input, select, textarea')).filter(function (control) {
			return control.type !== 'hidden' && !control.disabled;
		});
		let primerInvalido = null;
		controles.forEach(function (control) {
			clearFieldError(control);
			if (!control.checkValidity()) {
				setFieldError(control, 'Este campo es obligatorio.');
				if (!primerInvalido) {
					primerInvalido = control;
				}
			}
		});
		if (!primerInvalido) {
			return;
		}
		event.preventDefault();
		focusControl(primerInvalido);
		primerInvalido.scrollIntoView({ behavior: 'smooth', block: 'center' });
	}

	function focusFirstServerError() {
		if (!form) {
			return;
		}
		const firstErrorField = form.querySelector('.th-field--error');
		if (!firstErrorField) {
			return;
		}
		const control = firstErrorField.querySelector('input, select, textarea');
		if (!control) {
			return;
		}
		focusControl(control);
		firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
	}

	pacientesSeleccionadosTbody.addEventListener('click', function (e) {
		if (!puedeGestionarPacientes()) return;
		const btn = e.target.closest('[data-remove-paciente]');
		if (!btn) return;
		const idx = Number(btn.dataset.removePaciente);
		pacientesSeleccionados.splice(idx, 1);
		renderPacientesSeleccionados();
	});

	empleadosSeleccionadosTbody.addEventListener('click', function (e) {
		if (isReadOnly) return;
		const btn = e.target.closest('[data-remove-empleado]');
		if (!btn) return;
		const idx = Number(btn.dataset.removeEmpleado);
		empleadosSeleccionados.splice(idx, 1);
		renderEmpleadosSeleccionados();
	});

	if (!isReadOnly) {
		if (buscarPacienteBtn) buscarPacienteBtn.addEventListener('click', buscarPacientes);
		if (buscarPacienteInput) buscarPacienteInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); buscarPacientes(); } });
		if (form) {
			form.addEventListener('submit', validarFormularioAntesDeEnviar);
			form.querySelectorAll('input, select, textarea').forEach(function (control) {
				control.addEventListener('input', function () { clearFieldError(control); });
				control.addEventListener('change', function () { clearFieldError(control); });
			});
		}
	}

	if (!isReadOnly && limpiarPacienteBtn) {
		limpiarPacienteBtn.addEventListener('click', function () {
			if (criterioPaciente) {
				criterioPaciente.value = 'nombre';
			}
			if (buscarPacienteInput) {
				buscarPacienteInput.value = '';
				buscarPacienteInput.focus();
			}
			pacientesResultados.innerHTML = '';
		});
	}

	if (!isReadOnly && criterioPaciente) {
		criterioPaciente.addEventListener('change', function () {
			if (!buscarPacienteInput) {
				return;
			}
			buscarPacienteInput.placeholder = criterioPaciente.value === 'identidad'
				? 'Buscar paciente por identidad'
				: 'Buscar paciente por nombre';
			buscarPacienteInput.value = '';
			pacientesResultados.innerHTML = '';
		});
	}

	empleadoSearchTom = initEmpleadoSearchSelect();

	if (!isReadOnly && limpiarEmpleadoBtn) {
		limpiarEmpleadoBtn.addEventListener('click', function () {
			if (criterioEmpleado) {
				criterioEmpleado.value = 'nombre';
			}
			if (empleadoSearchTom) {
				empleadoSearchTom.clear(true);
				empleadoSearchTom.clearOptions();
				updateEmpleadoSearchPlaceholder('Buscar empleado por nombre');
			}
		});
	}

	if (!isReadOnly && criterioEmpleado) {
		criterioEmpleado.addEventListener('change', function () {
			if (!empleadoSearchTom) {
				return;
			}
			empleadoSearchTom.clear(true);
			empleadoSearchTom.clearOptions();
			updateEmpleadoSearchPlaceholder(
				criterioEmpleado.value === 'identidad'
					? 'Buscar empleado por identidad'
					: 'Buscar empleado por nombre'
			);
		});
	}

	if (btnCancelar && urls.cancelar) {
		btnCancelar.addEventListener('click', function () {
			window.location.href = urls.cancelar;
		});
	}

	function syncModoPacientes(options) {
		const opts = options || {};
		const clearOnDisable = Boolean(opts.clearOnDisable);
		const habilitado = puedeGestionarPacientes();
		if (pacientesSearch) {
			pacientesSearch.style.display = habilitado ? '' : 'none';
		}
		if (!habilitado) {
			pacientesResultados.innerHTML = '';
			if (clearOnDisable && !isReadOnly) {
				pacientesSeleccionados = [];
			}
		}
		renderPacientesSeleccionados();
	}

	if (tipoSolicitudSelect && !isReadOnly) {
		tipoSolicitudSelect.addEventListener('change', function () {
			syncModoPacientes({ clearOnDisable: true });
		});
	}

	if (isReadOnly && form) {
		form.querySelectorAll('input, select, textarea, button').forEach(function (control) {
			if (control.id === 'th-btn-cancelar-solicitud') {
				return;
			}
			if (control.tomselect) {
				control.tomselect.disable();
			}
			control.disabled = true;
		});
	}

	if (puntoSelect) {
		puntoSelect.addEventListener('change', syncAreaSolicitante);
	}
	syncAreaSolicitante();
	syncModoPacientes({ clearOnDisable: false });
	renderEmpleadosSeleccionados();
	focusFirstServerError();
})();
