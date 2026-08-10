(function () {
	const config = window.sgTransporteHospitalarioDashboard || {};
	const activeTab = String(config.activeTab || '');

	if (activeTab !== 'solicitud' && activeTab !== 'autorizacion' && activeTab !== 'viaje_construccion') {
		return;
	}

	if (!window.jQuery || !jQuery.fn.DataTable) {
		return;
	}

	if (activeTab === 'solicitud') {
		const tablaNode = document.getElementById('th-solicitudes-activas-table');
		if (!tablaNode) {
			return;
		}

		const tabla = jQuery(tablaNode).DataTable({
			order: [[1, 'desc']],
			language: {
				emptyTable: config.emptyTable || 'No hay registros disponibles.'
			},
			createdRow: function (row) {
				const labels = ['Número solicitud', 'Fecha', 'Área solicitante', 'Tipo solicitud', 'Prioridad', 'Proceso', 'Acción'];
				row.querySelectorAll('td').forEach(function (cell, index) {
					cell.setAttribute('data-label', labels[index] || '');
				});
			}
		});

		function aplicarFiltro(selectId, columnIndex) {
			const node = document.getElementById(selectId);
			if (!node) return;
			node.addEventListener('change', function () {
				const value = node.value || '';
				tabla.column(columnIndex).search(value).draw();
			});
		}

		aplicarFiltro('th-filtro-proceso', 5);
		aplicarFiltro('th-filtro-area', 2);
		aplicarFiltro('th-filtro-tipo', 3);
		return;
	}

		const tablaNode = document.getElementById('th-autorizacion-pendientes-table');
		if (tablaNode) {
			const modalNodes = document.querySelectorAll('#th-solicitud-modal');
			if (modalNodes.length > 1) {
				modalNodes.forEach(function (node, index) {
					if (index > 0 && node.parentNode) {
						node.parentNode.removeChild(node);
					}
				});
			}

			const searchInput = document.getElementById('th-autorizacion-busqueda');
			const searchButton = document.getElementById('th-autorizacion-buscar');
			const clearButton = document.getElementById('th-autorizacion-limpiar');
			const criterioSelect = document.getElementById('th-autorizacion-criterio');
			const modalNode = document.getElementById('th-solicitud-modal');
			const modalContent = document.getElementById('th-solicitud-modal-content');
			const modalTitulo = document.getElementById('th-solicitud-modal-title');
			const modalSubtitulo = document.getElementById('th-solicitud-modal-subtitle');
			const modalCerrarBtns = modalNode ? modalNode.querySelectorAll('[data-modal-close]') : [];

			let modalSolicitudActiva = null;
			let modalRowActiva = null;
			let modalDetalleActiva = null;

			const tablaAutorizacion = jQuery(tablaNode).DataTable({
				order: [[1, 'desc']],
				language: {
					emptyTable: config.emptyAutorizacionTable || 'No hay solicitudes pendientes disponibles para autorización.'
				},
				createdRow: function (row) {
					const labels = ['Número', 'Fecha', 'Prioridad', 'Punto de solicitud', 'Tipo', 'Pacientes', 'Destino', 'Acciones'];
					row.querySelectorAll('td').forEach(function (cell, index) {
						cell.setAttribute('data-label', labels[index] || '');
					});
				}
			});

			function escapeHtml(value) {
				return String(value == null ? '' : value).replace(/[&<>'"]/g, function (character) {
					return ({
						'&': '&amp;',
						'<': '&lt;',
						'>': '&gt;',
						'"': '&quot;',
						"'": '&#39;'
					})[character];
				});
			}

			function getCookie(name) {
				const matches = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
				return matches ? decodeURIComponent(matches[1]) : '';
			}

			async function requestJson(url, payload) {
				const response = await fetch(url, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						'X-Requested-With': 'XMLHttpRequest',
						'X-CSRFToken': getCookie('csrftoken')
					},
					body: JSON.stringify(payload || {})
				});
				const data = await response.json().catch(function () {
					return {};
				});
				if (!response.ok) {
					throw new Error(data.message || data.detail || 'No se pudo completar la solicitud.');
				}
				return data;
			}

			async function requestGetJson(url) {
				const response = await fetch(url, {
					headers: {
						'X-Requested-With': 'XMLHttpRequest'
					}
				});
				const data = await response.json().catch(function () {
					return {};
				});
				if (!response.ok) {
					throw new Error(data.message || data.detail || 'No se pudo cargar el detalle de la solicitud.');
				}
				return data;
			}

			function renderLista(items, emptyText) {
				if (!items || !items.length) {
					return '<div class="th-solicitud-modal__empty">' + escapeHtml(emptyText) + '</div>';
				}
				return '<div class="th-solicitud-modal__list">' + items.join('') + '</div>';
			}

			function renderMetaItem(label, value, extraClass) {
				return '<div class="th-solicitud-modal__meta-item' + (extraClass ? ' ' + extraClass : '') + '">'
					+ '<span>' + escapeHtml(label) + '</span>'
					+ '<strong>' + escapeHtml(value || '-') + '</strong>'
					+ '</div>';
			}

			function renderDetalleSolicitud(data) {
				const pacientes = Array.isArray(data.pacientes) ? data.pacientes : [];
				const personal = Array.isArray(data.personal) ? data.personal : [];
				const motivo = String(data.motivo || data.motivos || '').trim();
				const observaciones = String(data.observaciones || data.observacion || '').trim();
				const prioridadTexto = String(data.prioridad || '-').trim();
				const esUrgente = /urgente/i.test(prioridadTexto);
				const puntoSolicitud = String(data.punto_solicitud || data.punto || '-').trim();
				const origen = String(data.origen || '-').trim();
				const destino = String(data.destino || '-').trim();
				const solicitante = data.solicitante || {};
				const solicitanteTexto = String(solicitante.nombre || '-').trim();
				const pacientesHtml = pacientes.map(function (item) {
					return '<article class="th-solicitud-modal__item">'
						+ '<strong>' + escapeHtml(item.paciente || '-') + '</strong>'
						+ '<div>' + escapeHtml(item.identidad || '-') + '</div>'
						+ '<small>' + escapeHtml(item.solicitud || data.numero_solicitud || '-') + '</small>'
						+ '</article>';
				});
				const personalHtml = personal.map(function (item) {
					return '<article class="th-solicitud-modal__item">'
						+ '<strong>' + escapeHtml(item.nombre || '-') + '</strong>'
						+ '<div>' + escapeHtml(item.cargo || '-') + '</div>'
						+ '<small>' + escapeHtml(item.unidad || '-') + '</small>'
						+ '</article>';
				});
				return ''
					+ '<div class="th-solicitud-modal__hero">'
					+ '<div class="th-solicitud-modal__hero-main">'
					+ '<span class="th-solicitud-modal__eyebrow">Detalle de solicitud</span>'
					+ '<h5>Solicitud #' + escapeHtml(data.numero_solicitud || data.numero || '-') + '</h5>'
					+ '<p>Consulta rápida de la solicitud antes de autorizar o anular.</p>'
					+ '</div>'
					+ '</div>'
					+ '<div class="th-solicitud-modal__grid">'
					+ '<section class="th-solicitud-modal__section">'
					+ '<h5>Información General</h5>'
					+ '<div class="th-solicitud-modal__meta">'
					+ renderMetaItem('Número de solicitud', data.numero_solicitud || data.numero || '-')
					+ renderMetaItem('Estado', data.estado || data.proceso || '-')
					+ renderMetaItem('Prioridad', prioridadTexto, esUrgente ? 'th-solicitud-modal__meta-item--urgent' : '')
					+ renderMetaItem('Punto de solicitud', puntoSolicitud, 'th-solicitud-modal__meta-item--wide')
						+ renderMetaItem('Origen', origen)
						+ renderMetaItem('Usuario/Empleado', solicitanteTexto)
					+ renderMetaItem('Destino', destino, 'th-solicitud-modal__meta-item--wide')
					+ '</div>'
					+ '</section>'
					+ '<section class="th-solicitud-modal__section">'
					+ '<h5>Pacientes</h5>'
					+ renderLista(pacientesHtml, 'Sin pacientes asociados.')
					+ '</section>'
					+ '<section class="th-solicitud-modal__section">'
					+ '<h5>Personal solicitado</h5>'
					+ renderLista(personalHtml, 'Sin personal asociado.')
					+ '</section>'
					+ '<section class="th-solicitud-modal__section">'
					+ '<h5>Motivo de la solicitud</h5>'
					+ renderLista(motivo ? ['<div class="th-solicitud-modal__textblock">' + escapeHtml(motivo) + '</div>'] : [], 'Sin motivo registrado.')
					+ '</section>'
					+ '<section class="th-solicitud-modal__section">'
					+ '<h5>Observaciones</h5>'
					+ renderLista(observaciones ? ['<div class="th-solicitud-modal__textblock">' + escapeHtml(observaciones) + '</div>'] : [], 'No hay observaciones registradas.')
					+ '</section>'
					+ '</div>';
			}

			function esperarCierreSwal() {
				return new Promise(function (resolve) {
					window.setTimeout(resolve, 180);
				});
			}

			async function solicitarMotivoAnulacion() {
				const resultado = await Swal.fire({
					title: 'Anular Solicitud',
					html: ''
						+ '<div class="th-solicitud-modal__content" style="padding:0;">'
						+ '<section class="th-solicitud-modal__section">'
						+ '<h5>Motivo de la anulación</h5>'
						+ '<p style="margin:0 0 0.6rem;color:#475569;font-size:1.25rem;">Explique brevemente el motivo por el cual se anula esta solicitud.</p>'
						+ '<textarea id="th-anulacion-motivo" class="th-input" rows="5" placeholder="Describa el motivo por el cual la solicitud será anulada..." style="width:100%;min-height:12rem;resize:vertical;"></textarea>'
						+ '</section>'
						+ '</div>',
					showCancelButton: true,
					confirmButtonText: '<i class="bi bi-arrow-right-circle"></i> Continuar',
					cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar',
					customClass: {
						popup: 'contenedor-modal',
						title: 'contener-modal-titulo',
						confirmButton: 'contener-modal-boton-confirmar',
						cancelButton: 'contener-modal-boton-cancelar'
					},
					didOpen: function () {
						const actionsContainer = document.querySelector('.swal2-actions');
						if (actionsContainer) {
							actionsContainer.classList.add('contener-modal-contenedor-botones-min');
						}
						const htmlContainer = document.querySelector('.swal2-html-container');
						if (htmlContainer) {
							htmlContainer.classList.add('contener-modal-contenedor-html');
						}
						const motivoInput = document.getElementById('th-anulacion-motivo');
						if (motivoInput) {
							motivoInput.focus();
						}
					},
					preConfirm: function () {
						const motivoInput = document.getElementById('th-anulacion-motivo');
						const motivo = String(motivoInput && motivoInput.value ? motivoInput.value : '').trim();
						if (!motivo) {
							Swal.showValidationMessage('El motivo de anulación es obligatorio.');
							return false;
						}
						return motivo;
					}
				});
				if (!resultado.isConfirmed) {
					return null;
				}
				return String(resultado.value || '').trim();
			}

			async function confirmarAnulacion(motivo) {
				const resultado = await Swal.fire({
					title: 'Confirmar anulación',
					icon: 'warning',
					html: ''
						+ '<div class="th-solicitud-modal__content" style="padding:0;">'
						+ '<section class="th-solicitud-modal__section">'
						+ '<p style="margin:0;color:#334155;font-size:1.3rem;line-height:1.5;">¿Confirma la anulación de esta solicitud? Esta acción retirará la solicitud del flujo operativo.</p>'
						+ '</section>'
						+ '<section class="th-solicitud-modal__section">'
						+ '<h5>Motivo ingresado</h5>'
						+ '<div class="th-solicitud-modal__textblock" style="white-space:pre-wrap;">' + escapeHtml(motivo) + '</div>'
						+ '</section>'
						+ '</div>',
					showCancelButton: true,
					confirmButtonText: '<i class="bi bi-check2-circle"></i> Sí, anular',
					cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Volver',
					customClass: {
						popup: 'contenedor-modal',
						title: 'contener-modal-titulo',
						confirmButton: 'contener-modal-boton-confirmar',
						cancelButton: 'contener-modal-boton-cancelar'
					},
					didOpen: function () {
						const actionsContainer = document.querySelector('.swal2-actions');
						if (actionsContainer) {
							actionsContainer.classList.add('contener-modal-contenedor-botones-min');
						}
						const htmlContainer = document.querySelector('.swal2-html-container');
						if (htmlContainer) {
							htmlContainer.classList.add('contener-modal-contenedor-html');
						}
					}
				});
				return resultado.isConfirmed;
			}

			async function cargarDetalleSolicitud(solicitudId) {
				if (!config.urlDetalleSolicitud || !modalContent) {
					return;
				}
				try {
					const respuesta = await requestGetJson(config.urlDetalleSolicitud + '?id=' + encodeURIComponent(solicitudId));
					const detalle = respuesta.data || {};
					if (!modalSolicitudActiva || String(modalSolicitudActiva) !== String(solicitudId)) {
						return;
					}
					modalDetalleActiva = detalle;
					if (window.sgThAutorizacion && typeof window.sgThAutorizacion.__setDetalleActiva === 'function') {
						window.sgThAutorizacion.__setDetalleActiva(detalle);
					}
					if (modalSubtitulo) {
						modalSubtitulo.textContent = 'Revisión individual en modo solo lectura';
					}
					modalContent.innerHTML = renderDetalleSolicitud(detalle);
				} catch (error) {
					modalContent.innerHTML = '<div class="th-solicitud-modal__empty">' + escapeHtml(error.message || 'No se pudo cargar el detalle de la solicitud.') + '</div>';
				}
			}

			function abrirModalSolicitud(row) {
				let detallePreCargado = arguments.length > 1 ? arguments[1] : null;
				if (!modalNode || !modalContent) {
					return;
				}
				const solicitudId = row ? String(row.dataset.solicitudId || '') : '';
				if (!solicitudId) {
					return;
				}
				modalSolicitudActiva = solicitudId;
				modalRowActiva = row || null;
				if (modalTitulo) {
					const numero = row && row.children[0] ? row.children[0].textContent.trim() : '-';
					modalTitulo.textContent = 'Detalle de solicitud #' + numero;
				}
				if (modalSubtitulo) {
					modalSubtitulo.textContent = 'Vista rápida en modo solo lectura';
				}
				modalContent.innerHTML = '<div class="th-solicitud-modal__loading"><i class="bi bi-hourglass-split"></i> Cargando detalle...</div>';
				modalNode.classList.add('is-open');
				modalNode.setAttribute('aria-hidden', 'false');
				document.body.classList.add('th-modal-open');
				if (detallePreCargado) {
					modalDetalleActiva = detallePreCargado;
					if (window.sgThAutorizacion && typeof window.sgThAutorizacion.__setDetalleActiva === 'function') {
						window.sgThAutorizacion.__setDetalleActiva(detallePreCargado);
					}
					modalContent.innerHTML = renderDetalleSolicitud(detallePreCargado);
				} else {
					void cargarDetalleSolicitud(solicitudId);
				}
			}

			function cerrarModalSolicitud() {
				if (!modalNode || !modalContent) {
					return;
				}
				modalNode.classList.remove('is-open');
				modalNode.setAttribute('aria-hidden', 'true');
				modalContent.innerHTML = '<div class="th-solicitud-modal__empty">Seleccione una solicitud para ver su detalle.</div>';
				document.body.classList.remove('th-modal-open');
				modalSolicitudActiva = null;
				modalRowActiva = null;
			}

			async function autorizarSolicitud(id, row) {
				if (!id || !config.urlAutorizarSolicitud) {
					return;
				}
				try {
					await requestJson(config.urlAutorizarSolicitud, { solicitud_id: id });
					if (row) {
						tablaAutorizacion.row(row).remove().draw(false);
					}
					if (modalSolicitudActiva && String(modalSolicitudActiva) === String(id)) {
						cerrarModalSolicitud();
					}
					window.location.reload();
				} catch (error) {
					notifyError(error.message || 'No se pudo autorizar la solicitud.');
				}
			}

			async function anularSolicitud(id, row) {
				if (!id || !config.urlProgramacionAnular) {
					return;
				}
				const rowContext = row || modalRowActiva || null;
				const detalleContext = modalDetalleActiva || null;
				if (modalNode && modalNode.classList.contains('is-open')) {
					cerrarModalSolicitud();
				}
				const motivo = await solicitarMotivoAnulacion();
				if (motivo === null) {
					await esperarCierreSwal();
					if (rowContext) {
						abrirModalSolicitud(rowContext, detalleContext);
					}
					return;
				}
				const confirmada = await confirmarAnulacion(motivo);
				if (!confirmada) {
					await esperarCierreSwal();
					if (rowContext) {
						abrirModalSolicitud(rowContext, detalleContext);
					}
					return;
				}
				try {
					await requestJson(config.urlProgramacionAnular, { solicitud_id: id, motivo: motivo });
					if (row) {
						tablaAutorizacion.row(row).remove().draw(false);
					}
					window.location.reload();
				} catch (error) {
					notifyError(error.message || 'No se pudo anular la solicitud.');
					if (rowContext) {
						abrirModalSolicitud(rowContext, detalleContext);
					}
				}
			}

			function aplicarBusqueda() {
				const columna = Number(criterioSelect && criterioSelect.value ? criterioSelect.value : 1);
				const valor = (searchInput && searchInput.value ? searchInput.value : '').trim();
				tablaAutorizacion.search('');
				tablaAutorizacion.columns().search('');
				if (valor) {
					tablaAutorizacion.column(columna).search(valor).draw();
					return;
				}
				tablaAutorizacion.draw();
			}

			tablaNode.addEventListener('click', function (event) {
				const verButton = event.target.closest('[data-ver-solicitud]');
				if (verButton) {
					const row = verButton.closest('tr');
					if (row) {
						abrirModalSolicitud(row);
					}
					return;
				}
				const autorizarButton = event.target.closest('[data-autorizar-solicitud]');
				if (autorizarButton) {
					const row = autorizarButton.closest('tr');
					const id = String(autorizarButton.dataset.autorizarSolicitud || row && row.dataset.solicitudId || '');
					void autorizarSolicitud(id, row || null);
					return;
				}
				const anularButton = event.target.closest('[data-anular-solicitud]');
				if (anularButton) {
					const row = anularButton.closest('tr');
					const id = String(anularButton.dataset.anularSolicitud || row && row.dataset.solicitudId || '');
					void anularSolicitud(id, row || null);
				}
			});

			if (searchButton) {
				searchButton.addEventListener('click', aplicarBusqueda);
			}
			if (searchInput) {
				searchInput.addEventListener('keydown', function (event) {
					if (event.key === 'Enter') {
						event.preventDefault();
						aplicarBusqueda();
					}
				});
			}
			if (clearButton) {
				clearButton.addEventListener('click', function () {
					if (criterioSelect) {
						criterioSelect.value = '1';
					}
					if (searchInput) {
						searchInput.value = '';
					}
					aplicarBusqueda();
				});
			}
			if (modalCerrarBtns && modalCerrarBtns.length) {
				modalCerrarBtns.forEach(function (button) {
					button.addEventListener('click', cerrarModalSolicitud);
				});
			}
			if (modalNode) {
				modalNode.addEventListener('click', function (event) {
					if (event.target && event.target.matches('[data-modal-close]')) {
						cerrarModalSolicitud();
					}
				});
			}
			const modalAutorizarBtn = document.getElementById('th-solicitud-modal-autorizar');
			const modalAnularBtn = document.getElementById('th-solicitud-modal-anular');
			window.sgThAutorizacion = {
				verSolicitud: function (button, event) {
					if (event) {
						event.preventDefault();
						event.stopPropagation();
					}
					const row = button ? button.closest('tr') : null;
					if (row) {
						abrirModalSolicitud(row);
					}
					return false;
				},
				autorizarSolicitud: function (button, event) {
					if (event) {
						event.preventDefault();
						event.stopPropagation();
					}
					const row = button ? button.closest('tr') : null;
					const id = String(button && button.dataset.autorizarSolicitud || row && row.dataset.solicitudId || '');
					void autorizarSolicitud(id, row || null);
					return false;
				},
				anularSolicitud: function (button, event) {
					if (event) {
						event.preventDefault();
						event.stopPropagation();
					}
					const row = button ? button.closest('tr') : null;
					const id = String(button && button.dataset.anularSolicitud || row && row.dataset.solicitudId || '');
					void anularSolicitud(id, row || null);
					return false;
				},
				cerrarModal: function (button, event) {
					if (event) {
						event.preventDefault();
						event.stopPropagation();
					}
					cerrarModalSolicitud();
					return false;
				},
				autorizarDesdeModal: function (button, event) {
					if (event) {
						event.preventDefault();
						event.stopPropagation();
					}
					if (modalRowActiva) {
						void autorizarSolicitud(String(modalSolicitudActiva || ''), modalRowActiva);
					}
					return false;
				},
				anularDesdeModal: function (button, event) {
					if (event) {
						event.preventDefault();
						event.stopPropagation();
					}
					if (modalRowActiva) {
						void anularSolicitud(String(modalSolicitudActiva || ''), modalRowActiva);
					}
					return false;
				}
				,
				__setDetalleActiva: function (detalle) {
					modalDetalleActiva = detalle || null;
				}
			};
		}
})();
