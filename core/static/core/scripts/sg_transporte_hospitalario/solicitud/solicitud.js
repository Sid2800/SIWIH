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

	const dom = {
		form: document.getElementById('solicitud-form'),
		areaSolicitanteInput: document.getElementById('id_area_solicitante'),
		puntoSelect: document.getElementById('id_punto_solicitud'),
		areaSolicitanteLabel: document.getElementById('th-area-solicitante'),
		tipoSolicitudSelect: document.getElementById('id_tipo_solicitud'),
		lugarSalidaSelect: document.getElementById('id_lugar_salida'),
		destinoSelect: document.getElementById('id_lugar_destino'),
		pacientesPayload: document.getElementById('id_pacientes_json'),
		empleadosPayload: document.getElementById('id_empleados_json'),
		pacientesCard: document.getElementById('th-pacientes-seleccionados') ? document.getElementById('th-pacientes-seleccionados').closest('.th-card') : null,
		pacientesResultadosTbody: document.getElementById('th-pacientes-resultados'),
		pacientesSeleccionadosTbody: document.getElementById('th-pacientes-seleccionados'),
		empleadosSeleccionadosTbody: document.getElementById('th-empleados-seleccionados'),
		pacientesSearch: {
			input: document.getElementById('th-buscar-paciente'),
			button: document.getElementById('th-btn-buscar-paciente'),
			panel: document.getElementById('th-pacientes-search'),
			criterio: document.getElementById('th-criterio-paciente'),
			limpiar: document.getElementById('th-btn-limpiar-paciente'),
		},
		empleadosSearch: {
			criterio: document.getElementById('th-criterio-empleado'),
			select: document.getElementById('th-buscar-empleado-select'),
			limpiar: document.getElementById('th-btn-limpiar-empleado'),
		},
		cancelarButton: document.getElementById('th-btn-cancelar-solicitud'),
	};

	if (!dom.pacientesPayload || !dom.empleadosPayload || !dom.pacientesResultadosTbody || !dom.pacientesSeleccionadosTbody || !dom.empleadosSeleccionadosTbody) {
		return;
	}

	const state = {
		pacientesSeleccionados: safeParse(dom.pacientesPayload.value, []),
		empleadosSeleccionados: safeParse(dom.empleadosPayload.value, []),
		empleadoSearchTom: null,
		empleadosBusquedaMap: {},
	};

	function safeParse(raw, defaultValue) {
		if (!raw) return defaultValue;
		try { return JSON.parse(raw); } catch (_) { return defaultValue; }
	}

	function formatInstitutionText(info) {
		if (!info) {
			return '';
		}
		return joinDisplayParts([
			info.nombre,
			normalizeDisplayValue(info.nivel),
			info.region,
		]);
	}

	function normalizeDisplayValue(value) {
		return String(value || '')
			.replace(/^Nivel\s*/i, '')
			.trim();
	}

	function formatPointText(info) {
		if (!info) {
			return '';
		}
		return joinDisplayParts([
			info.nombre,
			//info.nombre_corto,
			info.tipo,
			info.servicio,
			//info.servicio_corto,
			info.nivel,
			info.region,
		]);
	}

	function joinDisplayParts(parts) {
		const seen = new Set();
		return parts
			.map(function (part) {
				return String(part || '').trim();
			})
			.filter(function (part) {
				if (!part || part === '-') {
					return false;
				}
				if (seen.has(part)) {
					return false;
				}
				seen.add(part);
				return true;
			})
			.join(' | ');
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
		if (!dom.tipoSolicitudSelect || !tipoPacientesId) {
			return true;
		}
		return String(dom.tipoSolicitudSelect.value || '') === tipoPacientesId;
	}

	function puedeGestionarPacientes() {
		return !isReadOnly && esTipoPacientesSeleccionado();
	}

	function initTomSelect(selector, options) {
		const baseOptions = {
			valueField: 'value',
			labelField: 'text',
			searchField: ['text'],
			create: false,
			allowEmptyOption: false,
			sortField: [{ field: 'text', direction: 'asc' }],
		};
		const tomSelectOptions = Object.assign({}, baseOptions, options || {});
		const node = document.querySelector(selector);
		if (!node || !window.TomSelect) {
			return null;
		}
		if (node.tomselect) {
			return node.tomselect;
		}
		return new TomSelect(selector, tomSelectOptions);
	}

	hydrateSelectText(dom.destinoSelect, destinosInfo, formatInstitutionText);
	hydrateSelectText(dom.lugarSalidaSelect, destinosInfo, formatInstitutionText);
	hydrateSelectText(dom.puntoSelect, puntosInfo, formatPointText);

	initTomSelect('#id_punto_solicitud', { placeholder: 'Punto solicitud' });
	initTomSelect('#id_tipo_solicitud', { placeholder: 'Tipo solicitud' });
	initTomSelect('#id_prioridad', { placeholder: 'Prioridad' });
	initTomSelect('#id_lugar_salida', { placeholder: 'Lugar salida' });
	initTomSelect('#id_lugar_destino', { placeholder: 'Lugar destino' });

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

	function setSectionError(section, message) {
		if (!section) {
			return;
		}
		section.classList.add('th-card--error');
		let errorNode = section.querySelector('.th-card-errors--client');
		if (!errorNode) {
			errorNode = document.createElement('div');
			errorNode.className = 'th-card-errors th-card-errors--client';
			const title = section.querySelector('.th-card__title');
			if (title && title.parentNode) {
				title.insertAdjacentElement('afterend', errorNode);
			} else {
				section.appendChild(errorNode);
			}
		}
		errorNode.textContent = message || 'Este campo es obligatorio.';
	}

	function clearSectionError(section) {
		if (!section) {
			return;
		}
		const errorNode = section.querySelector('.th-card-errors--client');
		if (errorNode) {
			errorNode.remove();
		}
		if (!section.querySelector('.th-card-errors')) {
			section.classList.remove('th-card--error');
		}
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
		if (!dom.puntoSelect || !dom.areaSolicitanteLabel || !dom.areaSolicitanteInput) return;
		const selectedInfo = puntosInfo[String(dom.puntoSelect.value || '')] || null;
		const txt = selectedInfo ? selectedInfo.nombre : '';
		dom.areaSolicitanteLabel.textContent = txt || '';
		dom.areaSolicitanteInput.value = txt || '';
	}

	function syncHiddenInputs() {
		dom.pacientesPayload.value = JSON.stringify(state.pacientesSeleccionados);
		dom.empleadosPayload.value = JSON.stringify(state.empleadosSeleccionados);
	}

	function buildEmptyRow(colspan, message) {
		return '<tr><td colspan="' + colspan + '">' + escapeHtml(message) + '</td></tr>';
	}

	function buildTableCell(label, content) {
		return '<td data-label="' + escapeHtml(label) + '">' + content + '</td>';
	}

	function buildPacienteRow(paciente, idx) {
		const accion = puedeGestionarPacientes()
			? '<button type="button" class="th-btn" data-remove-paciente="' + idx + '"><i class="bi bi-dash-circle"></i> Quitar</button>'
			: '<span class="th-subtitle">-</span>';
		return '\n                <tr>'
			+ buildTableCell('Nombre', escapeHtml(paciente.nombre || '-'))
			+ buildTableCell('Expediente', escapeHtml(paciente.expediente || '-'))
			+ buildTableCell('Ingreso', escapeHtml(paciente.ingreso || '-'))
			+ buildTableCell('Acción', accion)
			+ '\n                </tr>';
	}

	function buildPacienteResultadoRow(paciente, idx) {
		const yaEnOtraSolicitud = Boolean(paciente.solicitud_numero);
		const estadoSolicitud = paciente.solicitud_estado ? ' (' + escapeHtml(paciente.solicitud_estado) + ')' : '';
		const referenciaSolicitud = yaEnOtraSolicitud
			? '<small class="th-subtitle">Ya está en otra solicitud: <strong>' + escapeHtml(paciente.solicitud_numero) + '</strong>' + estadoSolicitud + '</small>'
			: '';
		const accion = yaEnOtraSolicitud
			? '<span class="th-subtitle">Bloqueado</span>'
			: '<button type="button" class="th-btn" data-add-paciente="' + idx + '"><i class="bi bi-plus-circle"></i> Agregar</button>';
		return '\n                <tr>'
			+ buildTableCell('Nombre', escapeHtml(paciente.nombre || '-') + (referenciaSolicitud ? '<br>' + referenciaSolicitud : ''))
			+ buildTableCell('Expediente', escapeHtml(paciente.expediente || '-'))
			+ buildTableCell('Ingreso', escapeHtml(paciente.ingreso || '-'))
			+ buildTableCell('Acción', accion)
			+ '\n                </tr>';
	}

	function buildEmpleadoRow(empleado, idx) {
		const accion = isReadOnly
			? '<span class="th-subtitle">-</span>'
			: '<button type="button" class="th-btn" data-remove-empleado="' + idx + '"><i class="bi bi-dash-circle"></i> Quitar</button>';
		return '\n                <tr>'
			+ buildTableCell('Nombre', escapeHtml(empleado.nombre || '-'))
			+ buildTableCell('Cargo', escapeHtml(empleado.cargo || '-'))
			+ buildTableCell('Acción', accion)
			+ '\n                </tr>';
	}

	function renderPacientesSeleccionados() {
		clearSectionError(dom.pacientesCard);
		if (!state.pacientesSeleccionados.length) {
			dom.pacientesSeleccionadosTbody.innerHTML = buildEmptyRow(4, 'No hay pacientes seleccionados.');
			syncHiddenInputs();
			return;
		}

		dom.pacientesSeleccionadosTbody.innerHTML = state.pacientesSeleccionados.map(buildPacienteRow).join('');
		syncHiddenInputs();
	}

	function renderEmpleadosSeleccionados() {
		if (!state.empleadosSeleccionados.length) {
			dom.empleadosSeleccionadosTbody.innerHTML = buildEmptyRow(3, 'No hay personal seleccionado.');
			syncHiddenInputs();
			return;
		}

		dom.empleadosSeleccionadosTbody.innerHTML = state.empleadosSeleccionados.map(buildEmpleadoRow).join('');
		syncHiddenInputs();
	}

	function agregarPaciente(item) {
		if (item && item.solicitud_numero) {
			toastr.warning('El paciente ya pertenece a la solicitud ' + item.solicitud_numero + '.', 'Validación');
			return;
		}
		const exists = state.pacientesSeleccionados.some(function (p) {
			return String(p.paciente_id || '') === String(item.paciente_id || '') && String(p.ingreso_id || '') === String(item.ingreso_id || '');
		});
		if (exists) return;
		state.pacientesSeleccionados.push(item);
		renderPacientesSeleccionados();
	}

	function agregarEmpleado(item) {
		const exists = state.empleadosSeleccionados.some(function (e) {
			return String(e.empleado_id || '') === String(item.empleado_id || '');
		});
		if (exists) return;
		state.empleadosSeleccionados.push(item);
		renderEmpleadosSeleccionados();
	}

	async function buscarPacientes() {
		if (!puedeGestionarPacientes()) return;
		const q = (dom.pacientesSearch.input.value || '').trim();
		if (q.length < 2 || !urls.buscarPacientes) return;
		setButtonLoading(dom.pacientesSearch.button, true);
		const tipo = (dom.pacientesSearch.criterio && dom.pacientesSearch.criterio.value) ? dom.pacientesSearch.criterio.value : 'nombre';
		const params = new URLSearchParams();
		params.append('q', q);
		params.append('tipo', tipo);
		try {
			const resp = await fetch(urls.buscarPacientes + '?' + params.toString());
			const payload = await resp.json();
			const rows = payload.data || [];
			if (!rows.length) {
				dom.pacientesResultadosTbody.innerHTML = buildEmptyRow(4, 'Sin resultados.');
				toastr.info('No se encontraron pacientes con ese criterio.', 'Información');
				return;
			}
			dom.pacientesResultadosTbody.innerHTML = rows.map(function (p, idx) {
				return buildPacienteResultadoRow(p, idx);
			}).join('');
			dom.pacientesResultadosTbody.querySelectorAll('[data-add-paciente]').forEach(function (btn) {
				btn.addEventListener('click', function () {
					if (!puedeGestionarPacientes()) return;
					agregarPaciente(rows[Number(btn.dataset.addPaciente)]);
				});
			});
		} catch (_) {
			toastr.warning('Ocurrió un problema al buscar pacientes.', 'Aviso');
		} finally {
			setButtonLoading(dom.pacientesSearch.button, false);
		}
	}

	function initEmpleadoSearchSelect() {
		if (!dom.empleadosSearch.select || !window.TomSelect || dom.empleadosSearch.select.tomselect || isReadOnly) {
			return dom.empleadosSearch.select ? dom.empleadosSearch.select.tomselect : null;
		}
		return initTomSelect('#th-buscar-empleado-select', {
			placeholder: 'Buscar empleado por nombre',
			maxItems: 1,
			maxOptions: 10,
			loadThrottle: 250,
			load: function (query, callback) {
				if (!query || query.trim().length < 2 || !urls.buscarEmpleados) {
					callback([]);
					return;
				}
				const tipo = (dom.empleadosSearch.criterio && dom.empleadosSearch.criterio.value) ? dom.empleadosSearch.criterio.value : 'nombre';
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
							state.empleadosBusquedaMap[String(row.empleado_id)] = row;
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
					const item = state.empleadosBusquedaMap[String(value || '')];
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
		if (!state.empleadoSearchTom) {
			return;
		}
		state.empleadoSearchTom.settings.placeholder = texto;
		if (state.empleadoSearchTom.control_input) {
			state.empleadoSearchTom.control_input.placeholder = texto;
		}
	}

	function validarFormularioAntesDeEnviar(event) {
		if (!dom.form || isReadOnly) {
			return;
		}
		clearSectionError(dom.pacientesCard);
		const controles = Array.from(dom.form.querySelectorAll('input, select, textarea')).filter(function (control) {
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
		if (!primerInvalido && esTipoPacientesSeleccionado() && !state.pacientesSeleccionados.length) {
			setSectionError(dom.pacientesCard, 'Debe seleccionar al menos un paciente para este tipo de solicitud.');
			primerInvalido = dom.pacientesSearch.input || dom.pacientesSearch.button || dom.tipoSolicitudSelect;
		}
		if (!primerInvalido) {
			return;
		}
		event.preventDefault();
		focusControl(primerInvalido);
		primerInvalido.scrollIntoView({ behavior: 'smooth', block: 'center' });
	}

	function bloquearEnterEnFormulario(event) {
		if (!dom.form || isReadOnly) {
			return;
		}
		if (event.key !== 'Enter') {
			return;
		}
		if (event.target && event.target.tagName === 'TEXTAREA') {
			return;
		}
		event.preventDefault();
	}

	function focusFirstServerError() {
		if (!dom.form) {
			return;
		}
		const firstErrorField = dom.form.querySelector('.th-field--error');
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

	dom.pacientesSeleccionadosTbody.addEventListener('click', function (e) {
		if (!puedeGestionarPacientes()) return;
		const btn = e.target.closest('[data-remove-paciente]');
		if (!btn) return;
		const idx = Number(btn.dataset.removePaciente);
		state.pacientesSeleccionados.splice(idx, 1);
		renderPacientesSeleccionados();
	});

	dom.empleadosSeleccionadosTbody.addEventListener('click', function (e) {
		if (isReadOnly) return;
		const btn = e.target.closest('[data-remove-empleado]');
		if (!btn) return;
		const idx = Number(btn.dataset.removeEmpleado);
		state.empleadosSeleccionados.splice(idx, 1);
		renderEmpleadosSeleccionados();
	});

	if (!isReadOnly) {
		if (dom.pacientesSearch.button) dom.pacientesSearch.button.addEventListener('click', buscarPacientes);
		if (dom.pacientesSearch.input) dom.pacientesSearch.input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); buscarPacientes(); } });
		if (dom.form) {
			dom.form.addEventListener('keydown', bloquearEnterEnFormulario);
			dom.form.addEventListener('submit', validarFormularioAntesDeEnviar);
			dom.form.querySelectorAll('input, select, textarea').forEach(function (control) {
				control.addEventListener('input', function () { clearFieldError(control); });
				control.addEventListener('change', function () { clearFieldError(control); });
			});
		}
	}

	if (!isReadOnly && dom.pacientesSearch.limpiar) {
		dom.pacientesSearch.limpiar.addEventListener('click', function () {
			if (dom.pacientesSearch.criterio) {
				dom.pacientesSearch.criterio.value = 'nombre';
			}
			if (dom.pacientesSearch.input) {
				dom.pacientesSearch.input.value = '';
				dom.pacientesSearch.input.focus();
			}
			dom.pacientesResultadosTbody.innerHTML = '';
		});
	}

	if (!isReadOnly && dom.pacientesSearch.criterio) {
		dom.pacientesSearch.criterio.addEventListener('change', function () {
			if (!dom.pacientesSearch.input) {
				return;
			}
			dom.pacientesSearch.input.placeholder = dom.pacientesSearch.criterio.value === 'identidad'
				? 'Buscar paciente por identidad'
				: 'Buscar paciente por nombre';
			dom.pacientesSearch.input.value = '';
			dom.pacientesResultadosTbody.innerHTML = '';
		});
	}

	state.empleadoSearchTom = initEmpleadoSearchSelect();

	if (!isReadOnly && dom.empleadosSearch.limpiar) {
		dom.empleadosSearch.limpiar.addEventListener('click', function () {
			if (dom.empleadosSearch.criterio) {
				dom.empleadosSearch.criterio.value = 'nombre';
			}
			if (state.empleadoSearchTom) {
				state.empleadoSearchTom.clear(true);
				state.empleadoSearchTom.clearOptions();
				updateEmpleadoSearchPlaceholder('Buscar empleado por nombre');
			}
		});
	}

	if (!isReadOnly && dom.empleadosSearch.criterio) {
		dom.empleadosSearch.criterio.addEventListener('change', function () {
			if (!state.empleadoSearchTom) {
				return;
			}
			state.empleadoSearchTom.clear(true);
			state.empleadoSearchTom.clearOptions();
			updateEmpleadoSearchPlaceholder(
				dom.empleadosSearch.criterio.value === 'identidad'
					? 'Buscar empleado por identidad'
					: 'Buscar empleado por nombre'
			);
		});
	}

	if (dom.cancelarButton && urls.cancelar) {
		dom.cancelarButton.addEventListener('click', function () {
			window.location.href = urls.cancelar;
		});
	}

	function syncModoPacientes(options) {
		const opts = options || {};
		const clearOnDisable = Boolean(opts.clearOnDisable);
		const habilitado = puedeGestionarPacientes();
		if (dom.pacientesSearch.panel) {
			dom.pacientesSearch.panel.style.display = habilitado ? '' : 'none';
		}
		if (!habilitado) {
			dom.pacientesResultadosTbody.innerHTML = '';
			if (clearOnDisable && !isReadOnly) {
				state.pacientesSeleccionados = [];
			}
		}
		renderPacientesSeleccionados();
	}

	if (dom.tipoSolicitudSelect && !isReadOnly) {
		dom.tipoSolicitudSelect.addEventListener('change', function () {
			syncModoPacientes({ clearOnDisable: true });
		});
	}

	if (isReadOnly && dom.form) {
		dom.form.querySelectorAll('input, select, textarea, button').forEach(function (control) {
			if (control.id === 'th-btn-cancelar-solicitud') {
				return;
			}
			if (control.tomselect) {
				control.tomselect.disable();
			}
			control.disabled = true;
		});
	}

	if (dom.puntoSelect) {
		dom.puntoSelect.addEventListener('change', syncAreaSolicitante);
	}
	syncAreaSolicitante();
	syncModoPacientes({ clearOnDisable: false });
	renderEmpleadosSeleccionados();
	focusFirstServerError();
})();
