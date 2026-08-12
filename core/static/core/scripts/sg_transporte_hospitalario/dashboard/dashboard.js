(function () {
	const configNode = document.getElementById('th-dashboard-config');
	let config = {};
	if (configNode) {
		try {
			config = JSON.parse(configNode.textContent || '{}') || {};
		} catch (error) {
			config = {};
		}
	}
	window.sgTransporteHospitalarioDashboard = config;
})();
(function () { 	const config = window.sgTransporteHospitalarioDashboard || {}; 	const activeTab = String(config.activeTab || '');  	if (activeTab !== 'solicitud' && activeTab !== 'autorizacion' && activeTab !== 'viaje_construccion') { 		return; 	}  	if (!window.jQuery || !jQuery.fn.DataTable) { 		return; 	}  	if (activeTab === 'solicitud') { 		const tablaNode = document.getElementById('th-solicitudes-activas-table'); 		if (!tablaNode) { 			return; 		}  		const tabla = jQuery(tablaNode).DataTable({ 			order: [[1, 'desc']], 			language: { 				emptyTable: config.emptyTable || 'No hay registros disponibles.' 			}, 			createdRow: function (row) { 				const labels = ['Número solicitud', 'Fecha', 'Creado por', 'Área solicitante', 'Tipo solicitud', 'Prioridad', 'Proceso', 'Acción']; 				row.querySelectorAll('td').forEach(function (cell, index) { 					cell.setAttribute('data-label', labels[index] || ''); 				}); 			} 		});  		function aplicarFiltro(selectId, columnIndex) { 			const node = document.getElementById(selectId); 			if (!node) return; 			node.addEventListener('change', function () { 				const value = node.value || ''; 				tabla.column(columnIndex).search(value).draw(); 			}); 		}  		aplicarFiltro('th-filtro-proceso', 6); 		aplicarFiltro('th-filtro-area', 3); 		aplicarFiltro('th-filtro-tipo', 4); 		return; 	}  		const tablaNode = document.getElementById('th-autorizacion-pendientes-table'); 		if (tablaNode) { 			const modalNodes = document.querySelectorAll('#th-solicitud-modal'); 			if (modalNodes.length > 1) { 				modalNodes.forEach(function (node, index) { 					if (index > 0 && node.parentNode) { 						node.parentNode.removeChild(node); 					} 				}); 			}  			const searchInput = document.getElementById('th-autorizacion-busqueda'); 			const searchButton = document.getElementById('th-autorizacion-buscar'); 			const clearButton = document.getElementById('th-autorizacion-limpiar'); 			const criterioSelect = document.getElementById('th-autorizacion-criterio'); 			const modalNode = document.getElementById('th-solicitud-modal'); 			const modalContent = document.getElementById('th-solicitud-modal-content'); 			const modalTitulo = document.getElementById('th-solicitud-modal-title'); 			const modalSubtitulo = document.getElementById('th-solicitud-modal-subtitle'); 			const modalCerrarBtns = modalNode ? modalNode.querySelectorAll('[data-modal-close]') : [];  			let modalSolicitudActiva = null; 			let modalRowActiva = null; 			let modalDetalleActiva = null;  			const tablaAutorizacion = jQuery(tablaNode).DataTable({ 				order: [[1, 'desc']], 				language: { 					emptyTable: config.emptyAutorizacionTable || 'No hay solicitudes pendientes disponibles para autorización.' 				}, 				createdRow: function (row) { 					const labels = ['Número', 'Fecha', 'Creado por', 'Prioridad', 'Punto de solicitud', 'Tipo', 'Pacientes', 'Destino', 'Acciones']; 					row.querySelectorAll('td').forEach(function (cell, index) { 						cell.setAttribute('data-label', labels[index] || ''); 					}); 				} 			});  			function escapeHtml(value) { 				return String(value == null ? '' : value).replace(/[&<>'"]/g, function (character) { 					return ({ 						'&': '&amp;', 						'<': '&lt;', 						'>': '&gt;', 						'"': '&quot;', 						"'": '&#39;' 					})[character]; 				}); 			}  			function getCookie(name) { 				const matches = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\/+^])/g, '\\$1') + '=([^;]*)')); 				return matches ? decodeURIComponent(matches[1]) : ''; 			}  			async function requestJson(url, payload) { 				const response = await fetch(url, { 					method: 'POST', 					headers: { 						'Content-Type': 'application/json', 						'X-Requested-With': 'XMLHttpRequest', 						'X-CSRFToken': getCookie('csrftoken') 					}, 					body: JSON.stringify(payload || {}) 				}); 				const data = await response.json().catch(function () { 					return {}; 				}); 				if (!response.ok) { 					throw new Error(data.message || data.detail || 'No se pudo completar la solicitud.'); 				} 				return data; 			}  			async function requestGetJson(url) { 				const response = await fetch(url, { 					headers: { 						'X-Requested-With': 'XMLHttpRequest' 					} 				}); 				const data = await response.json().catch(function () { 					return {}; 				}); 				if (!response.ok) { 					throw new Error(data.message || data.detail || 'No se pudo cargar el detalle de la solicitud.'); 				} 				return data; 			}  			function renderLista(items, emptyText) { 				if (!items || !items.length) { 					return '<div class="th-solicitud-modal__empty">' + escapeHtml(emptyText) + '</div>'; 				} 				return '<div class="th-solicitud-modal__list">' + items.join('') + '</div>'; 			}  			function renderMetaItem(label, value, extraClass) { 				return '<div class="th-solicitud-modal__meta-item' + (extraClass ? ' ' + extraClass : '') + '">' 					+ '<span>' + escapeHtml(label) + '</span>' 					+ '<strong>' + escapeHtml(value || '-') + '</strong>' 					+ '</div>'; 			}  			function renderDetalleSolicitud(data) { 				const pacientes = Array.isArray(data.pacientes) ? data.pacientes : []; 				const personal = Array.isArray(data.personal) ? data.personal : []; 				const motivo = String(data.motivo || data.motivos || '').trim(); 				const observaciones = String(data.observaciones || data.observacion || '').trim(); 				const prioridadTexto = String(data.prioridad || '-').trim(); 				const esUrgente = /urgente/i.test(prioridadTexto); 				const puntoSolicitud = String(data.punto_solicitud || data.punto || '-').trim(); 				const origen = String(data.origen || '-').trim(); 				const destino = String(data.destino || '-').trim(); 				const solicitante = data.solicitante || {}; 				const solicitanteTexto = String(solicitante.nombre || '-').trim(); 				const pacientesHtml = pacientes.map(function (item) { 					return '<article class="th-solicitud-modal__item">' 						+ '<strong>' + escapeHtml(item.paciente || '-') + '</strong>' 						+ '<div>' + escapeHtml(item.identidad || '-') + '</div>' 						+ '<small>' + escapeHtml(item.solicitud || data.numero_solicitud || '-') + '</small>' 						+ '</article>'; 				}); 				const personalHtml = personal.map(function (item) { 					return '<article class="th-solicitud-modal__item">' 						+ '<strong>' + escapeHtml(item.nombre || '-') + '</strong>' 						+ '<div>' + escapeHtml(item.cargo || '-') + '</div>' 						+ '<small>' + escapeHtml(item.unidad || '-') + '</small>' 						+ '</article>'; 				}); 				return '' 					+ '<div class="th-solicitud-modal__hero">' 					+ '<div class="th-solicitud-modal__hero-main">' 					+ '<span class="th-solicitud-modal__eyebrow">Detalle de solicitud</span>' 					+ '<h5>Solicitud #' + escapeHtml(data.numero_solicitud || data.numero || '-') + '</h5>' 					+ '<p>Consulta rápida de la solicitud antes de autorizar o anular.</p>' 					+ '</div>' 					+ '</div>' 					+ '<div class="th-solicitud-modal__grid">' 					+ '<section class="th-solicitud-modal__section">' 					+ '<h5>Información General</h5>' 					+ '<div class="th-solicitud-modal__meta">' 					+ renderMetaItem('Número de solicitud', data.numero_solicitud || data.numero || '-') 					+ renderMetaItem('Estado', data.estado || data.proceso || '-') 					+ renderMetaItem('Prioridad', prioridadTexto, esUrgente ? 'th-solicitud-modal__meta-item--urgent' : '') 					+ renderMetaItem('Punto de solicitud', puntoSolicitud, 'th-solicitud-modal__meta-item--wide') 						+ renderMetaItem('Origen', origen) 						+ renderMetaItem('Usuario/Empleado', solicitanteTexto) 					+ renderMetaItem('Destino', destino, 'th-solicitud-modal__meta-item--wide') 					+ '</div>' 					+ '</section>' 					+ '<section class="th-solicitud-modal__section">' 					+ '<h5>Pacientes</h5>' 					+ renderLista(pacientesHtml, 'Sin pacientes asociados.') 					+ '</section>' 					+ '<section class="th-solicitud-modal__section">' 					+ '<h5>Personal solicitado</h5>' 					+ renderLista(personalHtml, 'Sin personal asociado.') 					+ '</section>' 					+ '<section class="th-solicitud-modal__section">' 					+ '<h5>Motivo de la solicitud</h5>' 					+ renderLista(motivo ? ['<div class="th-solicitud-modal__textblock">' + escapeHtml(motivo) + '</div>'] : [], 'Sin motivo registrado.') 					+ '</section>' 					+ '<section class="th-solicitud-modal__section">' 					+ '<h5>Observaciones</h5>' 					+ renderLista(observaciones ? ['<div class="th-solicitud-modal__textblock">' + escapeHtml(observaciones) + '</div>'] : [], 'No hay observaciones registradas.') 					+ '</section>' 					+ '</div>'; 			}  			function esperarCierreSwal() { 				return new Promise(function (resolve) { 					window.setTimeout(resolve, 180); 				}); 			}  			async function solicitarMotivoAnulacion() { 				const resultado = await Swal.fire({ 					title: 'Anular Solicitud', 					html: '' 						+ '<div class="th-solicitud-modal__content" style="padding:0;">' 						+ '<section class="th-solicitud-modal__section">' 						+ '<h5>Motivo de la anulación</h5>' 						+ '<p style="margin:0 0 0.6rem;color:#475569;font-size:1.25rem;">Explique brevemente el motivo por el cual se anula esta solicitud.</p>' 						+ '<textarea id="th-anulacion-motivo" class="th-input" rows="5" placeholder="Describa el motivo por el cual la solicitud será anulada..." style="width:100%;min-height:12rem;resize:vertical;"></textarea>' 						+ '</section>' 						+ '</div>', 					showCancelButton: true, 					confirmButtonText: '<i class="bi bi-arrow-right-circle"></i> Continuar', 					cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Cancelar', 					customClass: { 						popup: 'contenedor-modal', 						title: 'contener-modal-titulo', 						confirmButton: 'contener-modal-boton-confirmar', 						cancelButton: 'contener-modal-boton-cancelar' 					}, 					didOpen: function () { 						const actionsContainer = document.querySelector('.swal2-actions'); 						if (actionsContainer) { 							actionsContainer.classList.add('contener-modal-contenedor-botones-min'); 						} 						const htmlContainer = document.querySelector('.swal2-html-container'); 						if (htmlContainer) { 							htmlContainer.classList.add('contener-modal-contenedor-html'); 						} 						const motivoInput = document.getElementById('th-anulacion-motivo'); 						if (motivoInput) { 							motivoInput.focus(); 						} 					}, 					preConfirm: function () { 						const motivoInput = document.getElementById('th-anulacion-motivo'); 						const motivo = String(motivoInput && motivoInput.value ? motivoInput.value : '').trim(); 						if (!motivo) { 							Swal.showValidationMessage('El motivo de anulación es obligatorio.'); 							return false; 						} 						return motivo; 					} 				}); 				if (!resultado.isConfirmed) { 					return null; 				} 				return String(resultado.value || '').trim(); 			}  			async function confirmarAnulacion(motivo) { 				const resultado = await Swal.fire({ 					title: 'Confirmar anulación', 					icon: 'warning', 					html: '' 						+ '<div class="th-solicitud-modal__content" style="padding:0;">' 						+ '<section class="th-solicitud-modal__section">' 						+ '<p style="margin:0;color:#334155;font-size:1.3rem;line-height:1.5;">¿Confirma la anulación de esta solicitud? Esta acción retirará la solicitud del flujo operativo.</p>' 						+ '</section>' 						+ '<section class="th-solicitud-modal__section">' 						+ '<h5>Motivo ingresado</h5>' 						+ '<div class="th-solicitud-modal__textblock" style="white-space:pre-wrap;">' + escapeHtml(motivo) + '</div>' 						+ '</section>' 						+ '</div>', 					showCancelButton: true, 					confirmButtonText: '<i class="bi bi-check2-circle"></i> Sí, anular', 					cancelButtonText: '<i class="bi bi-x-circle-fill"></i> Volver', 					customClass: { 						popup: 'contenedor-modal', 						title: 'contener-modal-titulo', 						confirmButton: 'contener-modal-boton-confirmar', 						cancelButton: 'contener-modal-boton-cancelar' 					}, 					didOpen: function () { 						const actionsContainer = document.querySelector('.swal2-actions'); 						if (actionsContainer) { 							actionsContainer.classList.add('contener-modal-contenedor-botones-min'); 						} 						const htmlContainer = document.querySelector('.swal2-html-container'); 						if (htmlContainer) { 							htmlContainer.classList.add('contener-modal-contenedor-html'); 						} 					} 				}); 				return resultado.isConfirmed; 			}  			async function cargarDetalleSolicitud(solicitudId) { 				if (!config.urlDetalleSolicitud || !modalContent) { 					return; 				} 				try { 					const respuesta = await requestGetJson(config.urlDetalleSolicitud + '?id=' + encodeURIComponent(solicitudId)); 					const detalle = respuesta.data || {}; 					if (!modalSolicitudActiva || String(modalSolicitudActiva) !== String(solicitudId)) { 						return; 					} 					modalDetalleActiva = detalle; 					if (window.sgThAutorizacion && typeof window.sgThAutorizacion.__setDetalleActiva === 'function') { 						window.sgThAutorizacion.__setDetalleActiva(detalle); 					} 					if (modalSubtitulo) { 						modalSubtitulo.textContent = 'Revisión individual en modo solo lectura'; 					} 					modalContent.innerHTML = renderDetalleSolicitud(detalle); 				} catch (error) { 					modalContent.innerHTML = '<div class="th-solicitud-modal__empty">' + escapeHtml(error.message || 'No se pudo cargar el detalle de la solicitud.') + '</div>'; 				} 			}  			function abrirModalSolicitud(row) { 				let detallePreCargado = arguments.length > 1 ? arguments[1] : null; 				if (!modalNode || !modalContent) { 					return; 				} 				const solicitudId = row ? String(row.dataset.solicitudId || '') : ''; 				if (!solicitudId) { 					return; 				} 				modalSolicitudActiva = solicitudId; 				modalRowActiva = row || null; 				if (modalTitulo) { 					const numero = row && row.children[0] ? row.children[0].textContent.trim() : '-'; 					modalTitulo.textContent = 'Detalle de solicitud #' + numero; 				} 				if (modalSubtitulo) { 					modalSubtitulo.textContent = 'Vista rápida en modo solo lectura'; 				} 				modalContent.innerHTML = '<div class="th-solicitud-modal__loading"><i class="bi bi-hourglass-split"></i> Cargando detalle...</div>'; 				modalNode.classList.add('is-open'); 				modalNode.setAttribute('aria-hidden', 'false'); 				document.body.classList.add('th-modal-open'); 				if (detallePreCargado) { 					modalDetalleActiva = detallePreCargado; 					if (window.sgThAutorizacion && typeof window.sgThAutorizacion.__setDetalleActiva === 'function') { 						window.sgThAutorizacion.__setDetalleActiva(detallePreCargado); 					} 					modalContent.innerHTML = renderDetalleSolicitud(detallePreCargado); 				} else { 					void cargarDetalleSolicitud(solicitudId); 				} 			}  			function cerrarModalSolicitud() { 				if (!modalNode || !modalContent) { 					return; 				} 				modalNode.classList.remove('is-open'); 				modalNode.setAttribute('aria-hidden', 'true'); 				modalContent.innerHTML = '<div class="th-solicitud-modal__empty">Seleccione una solicitud para ver su detalle.</div>'; 				document.body.classList.remove('th-modal-open'); 				modalSolicitudActiva = null; 				modalRowActiva = null; 			}  			async function autorizarSolicitud(id, row) { 				if (!id || !config.urlAutorizarSolicitud) { 					return; 				} 				try { 					await requestJson(config.urlAutorizarSolicitud, { solicitud_id: id }); 					if (row) { 						tablaAutorizacion.row(row).remove().draw(false); 					} 					if (modalSolicitudActiva && String(modalSolicitudActiva) === String(id)) { 						cerrarModalSolicitud(); 					} 					window.location.reload(); 				} catch (error) { 					notifyError(error.message || 'No se pudo autorizar la solicitud.'); 				} 			}  			async function anularSolicitud(id, row) { 				if (!id || !config.urlProgramacionAnular) { 					return; 				} 				const rowContext = row || modalRowActiva || null; 				const detalleContext = modalDetalleActiva || null; 				if (modalNode && modalNode.classList.contains('is-open')) { 					cerrarModalSolicitud(); 				} 				const motivo = await solicitarMotivoAnulacion(); 				if (motivo === null) { 					await esperarCierreSwal(); 					if (rowContext) { 						abrirModalSolicitud(rowContext, detalleContext); 					} 					return; 				} 				const confirmada = await confirmarAnulacion(motivo); 				if (!confirmada) { 					await esperarCierreSwal(); 					if (rowContext) { 						abrirModalSolicitud(rowContext, detalleContext); 					} 					return; 				} 				try { 					await requestJson(config.urlProgramacionAnular, { solicitud_id: id, motivo: motivo }); 					if (row) { 						tablaAutorizacion.row(row).remove().draw(false); 					} 					window.location.reload(); 				} catch (error) { 					notifyError(error.message || 'No se pudo anular la solicitud.'); 					if (rowContext) { 						abrirModalSolicitud(rowContext, detalleContext); 					} 				} 			}  			function aplicarBusqueda() { 				const columna = Number(criterioSelect && criterioSelect.value ? criterioSelect.value : 1); 				const valor = (searchInput && searchInput.value ? searchInput.value : '').trim(); 				tablaAutorizacion.search(''); 				tablaAutorizacion.columns().search(''); 				if (valor) { 					tablaAutorizacion.column(columna).search(valor).draw(); 					return; 				} 				tablaAutorizacion.draw(); 			}  			tablaNode.addEventListener('click', function (event) { 				const verButton = event.target.closest('[data-ver-solicitud]'); 				if (verButton) { 					const row = verButton.closest('tr'); 					if (row) { 						abrirModalSolicitud(row); 					} 					return; 				} 				const autorizarButton = event.target.closest('[data-autorizar-solicitud]'); 				if (autorizarButton) { 					const row = autorizarButton.closest('tr'); 					const id = String(autorizarButton.dataset.autorizarSolicitud || row && row.dataset.solicitudId || ''); 					void autorizarSolicitud(id, row || null); 					return; 				} 				const anularButton = event.target.closest('[data-anular-solicitud]'); 				if (anularButton) { 					const row = anularButton.closest('tr'); 					const id = String(anularButton.dataset.anularSolicitud || row && row.dataset.solicitudId || ''); 					void anularSolicitud(id, row || null); 				} 			});  			if (searchButton) { 				searchButton.addEventListener('click', aplicarBusqueda); 			} 			if (searchInput) { 				searchInput.addEventListener('keydown', function (event) { 					if (event.key === 'Enter') { 						event.preventDefault(); 						aplicarBusqueda(); 					} 				}); 			} 			if (clearButton) { 				clearButton.addEventListener('click', function () { 					if (criterioSelect) { 						criterioSelect.value = '1'; 					} 					if (searchInput) { 						searchInput.value = ''; 					} 					aplicarBusqueda(); 				}); 			} 			if (modalCerrarBtns && modalCerrarBtns.length) { 				modalCerrarBtns.forEach(function (button) { 					button.addEventListener('click', cerrarModalSolicitud); 				}); 			} 			if (modalNode) { 				modalNode.addEventListener('click', function (event) { 					if (event.target && event.target.matches('[data-modal-close]')) { 						cerrarModalSolicitud(); 					} 				}); 			} 			const modalAutorizarBtn = document.getElementById('th-solicitud-modal-autorizar'); 			const modalAnularBtn = document.getElementById('th-solicitud-modal-anular'); 			window.sgThAutorizacion = { 				verSolicitud: function (button, event) { 					if (event) { 						event.preventDefault(); 						event.stopPropagation(); 					} 					const row = button ? button.closest('tr') : null; 					if (row) { 						abrirModalSolicitud(row); 					} 					return false; 				}, 				autorizarSolicitud: function (button, event) { 					if (event) { 						event.preventDefault(); 						event.stopPropagation(); 					} 					const row = button ? button.closest('tr') : null; 					const id = String(button && button.dataset.autorizarSolicitud || row && row.dataset.solicitudId || ''); 					void autorizarSolicitud(id, row || null); 					return false; 				}, 				anularSolicitud: function (button, event) { 					if (event) { 						event.preventDefault(); 						event.stopPropagation(); 					} 					const row = button ? button.closest('tr') : null; 					const id = String(button && button.dataset.anularSolicitud || row && row.dataset.solicitudId || ''); 					void anularSolicitud(id, row || null); 					return false; 				}, 				cerrarModal: function (button, event) { 					if (event) { 						event.preventDefault(); 						event.stopPropagation(); 					} 					cerrarModalSolicitud(); 					return false; 				}, 				autorizarDesdeModal: function (button, event) { 					if (event) { 						event.preventDefault(); 						event.stopPropagation(); 					} 					if (modalRowActiva) { 						void autorizarSolicitud(String(modalSolicitudActiva || ''), modalRowActiva); 					} 					return false; 				}, 				anularDesdeModal: function (button, event) { 					if (event) { 						event.preventDefault(); 						event.stopPropagation(); 					} 					if (modalRowActiva) { 						void anularSolicitud(String(modalSolicitudActiva || ''), modalRowActiva); 					} 					return false; 				} 				, 				__setDetalleActiva: function (detalle) { 					modalDetalleActiva = detalle || null; 				} 			}; 		}  		if (activeTab === 'viaje_construccion') { 			const formNode = document.getElementById('th-viaje-construccion-form'); 			const tableNode = document.getElementById('th-viaje-construccion-table'); 			const searchNode = document.getElementById('th-viaje-buscar-solicitud'); 			const solicitudesCountNode = document.getElementById('th-viaje-solicitudes-count'); 			const pacientesCountNode = document.getElementById('th-viaje-pacientes-count'); 			const personalCountNode = document.getElementById('th-viaje-personal-count'); 			const solicitudesTotalNode = document.getElementById('th-viaje-solicitudes-total'); 			const pacientesTotalNode = document.getElementById('th-viaje-pacientes-total'); 			const personalTotalNode = document.getElementById('th-viaje-personal-total'); 			const viaticosTotalNode = document.getElementById('th-viaje-viaticos-total'); 			const resumenTextoNode = document.getElementById('th-viaje-resumen-texto'); 			const capacityAlertNode = document.getElementById('th-viaje-capacity-alert'); 			const seleccionadasListNode = document.getElementById('th-viaje-seleccionadas-list'); 			const personalListNode = document.getElementById('th-viaje-personal-list'); 			const personalSelectorNode = document.getElementById('th-viaje-personal-selector'); 			const viaticosListNode = document.getElementById('th-viaje-viaticos-list'); 			const viaticoSelectNode = document.getElementById('th-viaje-viatico-select'); 			const viaticoObservacionNode = document.getElementById('th-viaje-viatico-observacion'); 			const viaticoAgregarNode = document.getElementById('th-viaje-viatico-agregar'); 			const confirmarNode = document.getElementById('th-viaje-confirmar'); 			const feedbackNode = document.getElementById('th-viaje-feedback'); 			const vehiculoNode = formNode ? formNode.querySelector('[name="vehiculo"]') : null; 			const motoristaNode = formNode ? formNode.querySelector('[name="motorista"]') : null; 			const tipoViajeNode = formNode ? formNode.querySelector('[name="tipo_viaje"]') : null; 			const centroCostoNode = formNode ? formNode.querySelector('[name="centro_costo"]') : null; 			const personalHiddenNode = formNode ? formNode.querySelector('[name="personal_operativo_ids"]') : null; 			const viaticosHiddenNode = formNode ? formNode.querySelector('[name="viaticos_json"]') : null; 			const rows = tableNode ? Array.from(tableNode.querySelectorAll('tbody tr[data-viaje-solicitud-id]')) : []; 			const viajeItems = parseJsonScript('th-viaje-construccion-items'); 			const vehiculos = parseJsonScript('th-viaje-construccion-vehiculos'); 			const motoristas = parseJsonScript('th-viaje-construccion-motoristas'); 			const viaticos = parseJsonScript('th-viaje-construccion-viaticos'); 			const seleccionadas = new Map(); 			const personalSeleccionado = new Map(); 			const viaticosSeleccionados = new Map(); 			let personalTomSelect = null; 			let ignorarRemocionPersonalTomSelect = false; 			let vehiculoTomSelect = null; 			let motoristaTomSelect = null; 			let tipoViajeTomSelect = null; 			let viaticoTomSelect = null;  			function parseJsonScript(id) { 				const node = document.getElementById(id); 				if (!node) { 					return []; 				} 				try { 					return JSON.parse(node.textContent || '[]') || []; 				} catch (error) { 					return []; 				} 			}  			function normalizarTexto(value) { 				return String(value == null ? '' : value).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); 			}  			function escapeHtml(value) { 				return String(value == null ? '' : value).replace(/[&<>'"]/g, function (character) { 					return ({ 						'&': '&amp;', 						'<': '&lt;', 						'>': '&gt;', 						'"': '&quot;', 						"'": '&#39;' 					})[character]; 				}); 			}  			function getCookie(name) { 				const matches = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\/+^])/g, '\\$1') + '=([^;]*)')); 				return matches ? decodeURIComponent(matches[1]) : ''; 			}  			function prepararSelectTom(node, extras) { 				if (!node) { 					return null; 				} 				if (extras && extras.clearInitialSelection) { 					Array.from(node.options || []).forEach(function (option) { 						option.selected = false; 					}); 					node.selectedIndex = -1; 				} 				node.classList.remove('th-input'); 				node.classList.add('formularioCampo-select'); 				node.classList.add('th-viaje-select'); 				if (!window.TomSelect) { 					return null; 				} 				if (node.tomselect) { 					node.tomselect.destroy(); 				} 				return new TomSelect(node, Object.assign({ 					maxItems: 1, 					allowEmptyOption: true, 					create: false, 					searchField: ['text'], 					sortField: [{ field: 'text', direction: 'asc' }], 					placeholder: (node.querySelector('option[value=""]') && node.querySelector('option[value=""]').textContent.trim()) || node.getAttribute('aria-label') || 'Seleccione una opción' 				}, extras || {})); 			}  			function obtenerOpcionesSelect(node) { 				return Array.from(node ? node.options : []).filter(function (option) { 					return String(option.value || '') !== ''; 				}).map(function (option) { 					return { 						value: String(option.value || ''), 						text: String(option.textContent || '').trim() 					}; 				}); 			}  			async function requestJson(url, payload) { 				const response = await fetch(url, { 					method: 'POST', 					headers: { 						'Content-Type': 'application/json', 						'X-Requested-With': 'XMLHttpRequest', 						'X-CSRFToken': getCookie('csrftoken') 					}, 					body: JSON.stringify(payload || {}) 				}); 				const data = await response.json().catch(function () { 					return {}; 				}); 				if (!response.ok) { 					throw new Error(data.error || data.message || data.detail || 'No se pudo completar la solicitud.'); 				} 				return data; 			}  			function limpiarFeedback() { 				if (feedbackNode) { 					feedbackNode.hidden = true; 					feedbackNode.textContent = ''; 				} 				[vehiculoNode, motoristaNode, tipoViajeNode, centroCostoNode, viaticoSelectNode, personalSelectorNode].forEach(function (node) { 					if (node) { 						node.classList.remove('is-invalid'); 						if (node.tomselect && node.tomselect.control) { 							node.tomselect.control.classList.remove('is-invalid'); 						} 					} 				}); 			}  			function mostrarFeedback(mensaje) { 				if (!feedbackNode) { 					return; 				} 				feedbackNode.textContent = mensaje; 				feedbackNode.hidden = false; 			}  			function marcarInvalido(node) { 				if (node) { 					node.classList.add('is-invalid'); 					if (node.tomselect && node.tomselect.control) { 						node.tomselect.control.classList.add('is-invalid'); 					} 				} 			}  			function obtenerValorSeleccion(node) { 				if (!node) { 					return ''; 				} 				if (node.tomselect && typeof node.tomselect.getValue === 'function') { 					return String(node.tomselect.getValue() || ''); 				} 				return String(node.value || ''); 			}  			function obtenerTextoSeleccion(node, fallback) { 				if (!node || !node.selectedOptions || !node.selectedOptions.length) { 					if (node && node.tomselect && typeof node.tomselect.getValue === 'function') { 						const value = String(node.tomselect.getValue() || ''); 						const option = value ? node.tomselect.options[value] : null; 						if (option && option.text) { 							return String(option.text).trim(); 						} 					} 					return fallback || '-'; 				} 				return String(node.selectedOptions[0].textContent || fallback || '-').trim(); 			}  			function formatearOrigenes(origenes) { 				if (!Array.isArray(origenes) || !origenes.length) { 					return 'Sin origen registrado'; 				} 				return origenes.map(function (origen) { 					return [origen.numero || '-', origen.punto || '-'].join(' · '); 				}).join(' | '); 			}  			function obtenerPersonalSugerido() { 				const agrupado = new Map(); 				seleccionadas.forEach(function (solicitud) { 					(solicitud.personal || []).forEach(function (personalItem) { 						const personalId = String(personalItem.id || personalItem.empleado_id || ''); 						if (!personalId) { 							return; 						} 						const existente = agrupado.get(personalId) || { 							id: Number(personalItem.id || personalItem.empleado_id), 							nombre: personalItem.nombre || '-', 							cargo: personalItem.cargo || '', 							dni: personalItem.dni || '', 							fuente: 'Sugerido', 							origenes: [] 						}; 						existente.origenes.push({ 							numero: solicitud.numero, 							punto: solicitud.punto_corto || solicitud.punto 						}); 						agrupado.set(personalId, existente); 					}); 				}); 				return Array.from(agrupado.values()); 			}  			function etiquetaPersonal(item) { 				if (!item) { 					return 'Adicional'; 				} 				if (item.fuente === 'Manual') { 					return 'Adicional'; 				} 				const origenes = Array.isArray(item.origenes) ? item.origenes : []; 				if (!origenes.length) { 					return 'Sugerido'; 				} 				const origenPrincipal = origenes[0].numero || '-'; 				const extra = origenes.length > 1 ? ' (+' + (origenes.length - 1) + ')' : ''; 				return 'Sugerido · ' + origenPrincipal + extra; 			}  			function sincronizarPersonalSugerido() { 				const manuales = new Map(); 				Array.from(personalSeleccionado.values()).forEach(function (item) { 					if (item.fuente === 'Manual') { 						manuales.set(String(item.id), { 							id: item.id, 							nombre: item.nombre, 							cargo: item.cargo || '', 							dni: item.dni || '', 							fuente: 'Manual', 							origenes: Array.isArray(item.origenes) ? item.origenes : [] 						}); 					} 				});  				const sugeridos = new Map(); 				seleccionadas.forEach(function (solicitud) { 					(solicitud.personal || []).forEach(function (personalItem) { 						const personalId = String(personalItem.id || personalItem.empleado_id || ''); 						if (!personalId) { 							return; 						} 						const existente = sugeridos.get(personalId) || { 							id: Number(personalItem.id || personalItem.empleado_id), 							nombre: personalItem.nombre || '-', 							cargo: personalItem.cargo || '', 							dni: personalItem.dni || '', 							fuente: 'Sugerido', 							origenes: [] 						}; 						existente.origenes.push({ 							numero: solicitud.numero, 							punto: solicitud.punto_corto || solicitud.punto 						}); 						sugeridos.set(personalId, existente); 					}); 				});  				const combinado = new Map(manuales); 				sugeridos.forEach(function (sugerido, personalId) { 					const manual = combinado.get(personalId); 					if (manual) { 						const origenes = [...(manual.origenes || []), ...(sugerido.origenes || [])]; 						const mapaOrigenes = new Map(); 						origenes.forEach(function (origen) { 							const clave = [origen.numero || '-', origen.punto || '-'].join('|'); 							mapaOrigenes.set(clave, origen); 						}); 						combinado.set(personalId, { 							id: manual.id, 							nombre: manual.nombre || sugerido.nombre, 							cargo: manual.cargo || sugerido.cargo || '', 							dni: manual.dni || sugerido.dni || '', 							fuente: 'Sugerido', 							origenes: Array.from(mapaOrigenes.values()) 						}); 						return; 					} 					combinado.set(personalId, sugerido); 				});  				personalSeleccionado.clear(); 				combinado.forEach(function (item, key) { 					personalSeleccionado.set(key, item); 				}); 			}  			function obtenerPersonalSeleccionadoArray() { 				return Array.from(personalSeleccionado.values()); 			}  			function actualizarEstadoPersonal(personalId, cambios) { 				const existente = personalSeleccionado.get(String(personalId)); 				if (!existente) { 					personalSeleccionado.set(String(personalId), cambios); 					return; 				} 				existente.nombre = cambios.nombre || existente.nombre; 				existente.cargo = cambios.cargo || existente.cargo; 				existente.dni = cambios.dni || existente.dni; 				existente.fuente = existente.fuente === 'Manual' ? 'Manual' : cambios.fuente || existente.fuente || 'Sugerido'; 				const origenes = [...(existente.origenes || []), ...(cambios.origenes || [])]; 				const mapaOrigenes = new Map(); 				origenes.forEach(function (origen) { 					const clave = [origen.numero || '-', origen.punto || '-'].join('|'); 					mapaOrigenes.set(clave, origen); 				}); 				existente.origenes = Array.from(mapaOrigenes.values()); 			}  			function obtenerPersonalOperativo() { 				return Array.from(personalSeleccionado.values()).map(function (item) { 					return item.id; 				}); 			}  			function actualizarHiddenPersonal() { 				if (personalHiddenNode) { 					personalHiddenNode.value = JSON.stringify(obtenerPersonalOperativo()); 				} 			}  			function actualizarHiddenViaticos() { 				if (viaticosHiddenNode) { 					viaticosHiddenNode.value = JSON.stringify(Array.from(viaticosSeleccionados.values()).map(function (item) { 						return { 							viatico_id: item.id, 							observacion: item.observacion || '' 						}; 					})); 				} 			}  			function renderSeleccionadas() { 				if (!seleccionadasListNode) return; 				if (!seleccionadas.size) { 					seleccionadasListNode.innerHTML = '<div class="th-viaje-empty">Seleccione solicitudes autorizadas para empezar la construcción.</div>'; 					return; 				} 				seleccionadasListNode.innerHTML = Array.from(seleccionadas.values()).map(function (item) { 					const origenTexto = item.punto || item.punto_corto || '-'; 					return '<article class="th-viaje-item">' 						+ '<div class="th-viaje-item__body">' 						+ '<div class="th-viaje-item__head">' 						+ '<strong>' + escapeHtml(item.numero) + '</strong>' 						+ '<span class="th-viaje-item__badge th-badge">' + escapeHtml(item.prioridad) + '</span>' 						+ '</div>' 						+ '<div class="th-viaje-item__meta">' 						+ '<span>' + escapeHtml(origenTexto) + '</span>' 						+ '<span>' + escapeHtml(item.destino) + '</span>' 						+ '<span>' + escapeHtml(item.pacientesCount + ' pacientes') + '</span>' 						+ '</div>' 						+ '</div>' 						+ '<button type="button" class="th-btn th-btn--ghost th-viaje-item__remove" data-remove-viaje-solicitud="' + escapeHtml(item.id) + '" aria-label="Quitar solicitud">X</button>' 						+ '</article>'; 				}).join(''); 			}  			function renderPersonal() { 				if (!personalListNode) return; 				if (!personalSeleccionado.size) { 					personalListNode.innerHTML = '<div class="th-viaje-empty">No hay personal agregado todavía.</div>'; 				} else { 					personalListNode.innerHTML = obtenerPersonalSeleccionadoArray().map(function (item) { 						const badgeTexto = etiquetaPersonal(item); 						const origenTexto = formatearOrigenes(item.origenes || []); 						return '<article class="th-viaje-item">' 							+ '<div class="th-viaje-item__body">' 							+ '<div class="th-viaje-item__head">' 							+ '<strong>' + escapeHtml(item.nombre) + '</strong>' 							+ '<span class="th-viaje-item__badge th-badge" title="' + escapeHtml(origenTexto) + '">' + escapeHtml(badgeTexto) + '</span>' 							+ '</div>' 							+ '<div class="th-viaje-item__meta">' 							+ '<span>' + escapeHtml(item.cargo || '-') + '</span>' 							+ '</div>' 							+ '</div>' 							+ '<button type="button" class="th-btn th-btn--ghost th-viaje-item__remove" data-remove-personal="' + escapeHtml(item.id) + '" aria-label="Quitar personal">X</button>' 							+ '</article>'; 					}).join(''); 				} 			}  			function limpiarSelectorPersonal(ignorarRemocion) { 				if (!personalTomSelect) { 					return; 				} 				if (ignorarRemocion) { 					ignorarRemocionPersonalTomSelect = true; 				} 				if (typeof personalTomSelect.clear === 'function') { 					personalTomSelect.clear(true); 				} 				if (typeof personalTomSelect.setTextboxValue === 'function') { 					personalTomSelect.setTextboxValue(''); 				} 				if (typeof personalTomSelect.refreshOptions === 'function') { 					personalTomSelect.refreshOptions(false); 				} 				if (ignorarRemocion) { 					ignorarRemocionPersonalTomSelect = false; 				} 			}  			function initSelectorPersonal() { 				if (!personalSelectorNode || !window.TomSelect) { 					return; 				} 				personalTomSelect = prepararSelectTom(personalSelectorNode, { 					maxItems: 1, 					placeholder: 'Buscar personal por nombre o identidad...', 					allowEmptyOption: true, 					openOnFocus: true, 					loadThrottle: 250, 					load: function (query, callback) { 						const termino = String(query || '').trim(); 						if (termino.length < 2 || !config.urlBuscarEmpleados) { 							callback([]); 							return; 						} 						const tipo = /^[0-9\-]+$/.test(termino) ? 'identidad' : 'nombre'; 						const params = new URLSearchParams(); 						params.append('q', termino); 						params.append('tipo', tipo); 						params.append('disponibles', '1'); 						fetch(config.urlBuscarEmpleados + '?' + params.toString(), { 							headers: { 								'X-Requested-With': 'XMLHttpRequest' 							} 						}) 							.then(function (response) { 								return response.ok ? response.json() : Promise.reject(); 							}) 							.then(function (payload) { 								const resultados = Array.isArray(payload && payload.data) ? payload.data : []; 								callback(resultados.map(function (item) { 									const texto = [item.nombre || '-', item.cargo || '-', item.unidad || '-'].filter(Boolean).join(' · '); 									return { 										value: String(item.empleado_id), 										text: texto, 										nombre: item.nombre || '-', 										cargo: item.cargo || '', 										dni: item.dni || '', 										unidad: item.unidad || '', 										unidad_corta: item.unidad_corta || '' 									}; 								})); 							}) 							.catch(function () { 								if (window.toastr) { 									toastr.warning('No fue posible consultar el personal.', 'Aviso'); 								} 								callback([]); 							}); 					}, 					onChange: function (value) { 						const personalId = String(value || ''); 						if (!personalId) { 							return; 						} 						const item = this.options && this.options[personalId] ? this.options[personalId] : null; 						if (!item) { 							limpiarSelectorPersonal(); 							return; 						} 						agregarPersonal(personalId, item); 						limpiarSelectorPersonal(true); 						this.refreshOptions(false); 					}, 					onItemRemove: function (value) { 						if (ignorarRemocionPersonalTomSelect) { 							ignorarRemocionPersonalTomSelect = false; 							return; 						} 						const personalId = String(value || ''); 						if (!personalId) { 							return; 						} 						if (personalSeleccionado.has(personalId)) { 							personalSeleccionado.delete(personalId); 							renderPersonal(); 							actualizarResumen(); 						} 					} 				}); 			}  			function initSelectsFormulario() { 				vehiculoTomSelect = prepararSelectTom(vehiculoNode, { 					items: [], 					clearInitialSelection: true, 					options: obtenerOpcionesSelect(vehiculoNode), 					placeholder: 'Seleccione una ambulancia' 				}); 				motoristaTomSelect = prepararSelectTom(motoristaNode, { 					items: [], 					clearInitialSelection: true, 					options: obtenerOpcionesSelect(motoristaNode), 					placeholder: 'Seleccione un motorista' 				}); 				tipoViajeTomSelect = prepararSelectTom(tipoViajeNode, { 					items: [], 					clearInitialSelection: true, 					options: obtenerOpcionesSelect(tipoViajeNode), 					placeholder: 'Seleccione un tipo de viaje' 				}); 				window.setTimeout(function () { 					if (vehiculoTomSelect) vehiculoTomSelect.clear(true); 					if (motoristaTomSelect) motoristaTomSelect.clear(true); 					if (tipoViajeTomSelect) tipoViajeTomSelect.clear(true); 				}, 0); 				viaticoTomSelect = prepararSelectTom(viaticoSelectNode, { 					placeholder: 'Seleccione un viático', 					options: viaticos.map(function (item) { 						return { 							value: String(item.id), 							text: item.codigo + ' - ' + item.nombre + ' | ' + item.monto_vigente 						}; 					}) 				}); 			}  			function renderViaticos() { 				if (!viaticosListNode) return; 				if (!viaticosSeleccionados.size) { 					viaticosListNode.innerHTML = '<div class="th-viaje-empty">Agregue viáticos al viaje.</div>'; 				} else { 					viaticosListNode.innerHTML = Array.from(viaticosSeleccionados.values()).map(function (item) { 						const fechaTexto = item.fecha_asignacion || item.fecha || 'Pendiente de confirmación'; 						return '<article class="th-viaje-item">' 							+ '<div class="th-viaje-item__body">' 							+ '<div class="th-viaje-item__head">' 							+ '<strong>' + escapeHtml(item.codigo + ' · ' + item.nombre) + '</strong>' 							+ '<span class="th-viaje-item__badge th-badge">' + escapeHtml(item.monto_vigente) + '</span>' 							+ '</div>' 							+ '<div class="th-viaje-item__meta">' 							+ '<span>' + escapeHtml(fechaTexto) + '</span>' 							+ '<span>' + escapeHtml(item.observacion || 'Sin observación') + '</span>' 							+ '</div>' 							+ '</div>' 							+ '<button type="button" class="th-btn th-btn--ghost th-viaje-item__remove" data-remove-viatico="' + escapeHtml(item.id) + '" aria-label="Quitar viático">X</button>' 							+ '</article>'; 					}).join(''); 				} 				if (viaticoTomSelect) { 					viaticoTomSelect.refreshOptions(false); 				} 			}  			function actualizarResumen() { 				const totalSolicitudes = seleccionadas.size; 				const totalPacientes = Array.from(seleccionadas.values()).reduce(function (sum, item) { 					return sum + Number(item.pacientesCount || 0); 				}, 0); 				const totalPersonal = personalSeleccionado.size; 				const totalViaticos = viaticosSeleccionados.size;  				if (solicitudesTotalNode) solicitudesTotalNode.textContent = String(totalSolicitudes); 				if (pacientesTotalNode) pacientesTotalNode.textContent = String(totalPacientes); 				if (personalTotalNode) personalTotalNode.textContent = String(totalPersonal); 				if (viaticosTotalNode) viaticosTotalNode.textContent = String(totalViaticos); 				if (capacityAlertNode) { 					const superaLimite = totalPacientes > 3; 					capacityAlertNode.hidden = !superaLimite; 					capacityAlertNode.innerHTML = superaLimite ? '<span class="th-viaje-status__label">Alerta</span><span class="th-viaje-status__value">' + escapeHtml('El viaje tiene ' + totalPacientes + ' pacientes y supera la cantidad recomendada de 3.') + '<br><small>Puede continuar si confirma la construcción del viaje.</small></span>' : ''; 				} 				actualizarHiddenPersonal(); 				actualizarHiddenViaticos(); 			}  			function sincronizarSeleccionTabla() { 				rows.forEach(function (row) { 					const id = String(row.dataset.viajeSolicitudId || ''); 					const checkbox = row.querySelector('[data-viaje-solicitud-checkbox]'); 					const selected = seleccionadas.has(id); 					row.classList.toggle('is-selected', selected); 					if (checkbox) checkbox.checked = selected; 				}); 			}  			function aplicarBusquedaSolicitudes() { 				const query = normalizarTexto(searchNode && searchNode.value ? searchNode.value : ''); 				rows.forEach(function (row) { 					const hayCoincidencia = !query || normalizarTexto(row.dataset.searchText || '').includes(query); 					row.style.display = hayCoincidencia ? '' : 'none'; 				}); 			}  			function agregarSolicitud(id) { 				const item = viajeItems.find(function (entry) { return String(entry.id) === String(id); }); 				if (!item) return; 				seleccionadas.set(String(item.id), item); 				sincronizarPersonalSugerido(); 				sincronizarSeleccionTabla(); 				renderSeleccionadas(); 				renderPersonal(); 				actualizarResumen(); 			}  			function quitarSolicitud(id) { 				seleccionadas.delete(String(id)); 				sincronizarPersonalSugerido(); 				sincronizarSeleccionTabla(); 				renderSeleccionadas(); 				actualizarResumen(); 			}  			function agregarPersonal(id, datos) { 				const item = datos || null; 				if (!item) return; 				const personalId = String(id || item.empleado_id || item.id || item.value || ''); 				if (!personalId) { 					return; 				} 				const existente = personalSeleccionado.get(personalId); 				if (existente) { 					existente.nombre = existente.nombre || item.nombre || '-'; 					existente.cargo = existente.cargo || item.cargo || ''; 					existente.dni = existente.dni || item.dni || ''; 					if (existente.fuente !== 'Sugerido') { 						existente.fuente = 'Manual'; 					} 				} else { 					personalSeleccionado.set(personalId, { 						id: Number(item.empleado_id || item.id || item.value), 						nombre: item.nombre || '-', 						cargo: item.cargo || '', 						dni: item.dni || '', 						fuente: 'Manual', 						origenes: [] 					}); 				} 				sincronizarPersonalSugerido(); 				renderPersonal(); 				actualizarResumen(); 			}  			function quitarPersonal(id) { 				const personalId = String(id); 				personalSeleccionado.delete(personalId); 				renderPersonal(); 				actualizarResumen(); 				if (personalTomSelect && typeof personalTomSelect.removeItem === 'function' && personalTomSelect.items && personalTomSelect.items.includes(personalId)) { 					personalTomSelect.removeItem(personalId, true); 				} 			}  			function agregarViatico() { 				const viaticoId = Number(obtenerValorSeleccion(viaticoSelectNode) || 0); 				if (!viaticoId) return; 				const item = viaticos.find(function (entry) { return Number(entry.id) === viaticoId; }); 				if (!item) return; 				const observacion = String(viaticoObservacionNode && viaticoObservacionNode.value ? viaticoObservacionNode.value : '').trim(); 				viaticosSeleccionados.set(String(item.id), { 					id: Number(item.id), 					codigo: item.codigo, 					nombre: item.nombre, 					monto_vigente: item.monto_vigente, 					observacion: observacion, 					fecha_asignacion: new Date().toLocaleString() 				}); 				if (viaticoObservacionNode) { 					viaticoObservacionNode.value = ''; 				} 				if (viaticoTomSelect) { 					viaticoTomSelect.clear(true); 				} else if (viaticoSelectNode) { 					viaticoSelectNode.value = ''; 				} 				renderViaticos(); 				actualizarResumen(); 			}  			function quitarViatico(id) { 				viaticosSeleccionados.delete(String(id)); 				renderViaticos(); 				actualizarResumen(); 			}  			async function confirmarViaje() { 				if (!config.urlProgramacionConfirmar || !formNode) { 					return; 				} 				limpiarFeedback(); 				const seleccionIds = Array.from(seleccionadas.keys()).map(function (value) { return Number(value); }); 				const missingFields = []; 				if (!seleccionIds.length) { 					missingFields.push('Seleccione al menos una solicitud.'); 				} 				if (!obtenerValorSeleccion(vehiculoNode)) { 					missingFields.push('Seleccione un vehículo.'); 					marcarInvalido(vehiculoNode); 				} 				if (!obtenerValorSeleccion(motoristaNode)) { 					missingFields.push('Seleccione un motorista.'); 					marcarInvalido(motoristaNode); 				} 				if (!obtenerValorSeleccion(tipoViajeNode)) { 					missingFields.push('Seleccione un tipo de viaje.'); 					marcarInvalido(tipoViajeNode); 				} 				if (!centroCostoNode || !String(centroCostoNode.value || '').trim()) { 					missingFields.push('Complete el centro de costo.'); 					marcarInvalido(centroCostoNode); 				} 				if (!personalSeleccionado.size) { 					missingFields.push('Agregue al menos un integrante operativo.'); 				} 				if (missingFields.length) { 					const mensaje = 'Complete los datos requeridos antes de construir el viaje.\n' + missingFields.join('\n'); 					mostrarFeedback(mensaje.replace(/\n/g, ' ')); 					await Swal.fire({ 						icon: 'warning', 						title: 'Datos requeridos', 						text: mensaje 					}); 					return; 				}  				const totalPacientes = Array.from(seleccionadas.values()).reduce(function (sum, item) { 					return sum + Number(item.pacientesCount || 0); 				}, 0); 				if (totalPacientes > 3) { 					const advertencia = await Swal.fire({ 						icon: 'warning', 						title: 'Advertencia', 						html: '<p style="margin:0 0 1rem;line-height:1.5;">El viaje tiene ' + escapeHtml(String(totalPacientes)) + ' pacientes y supera la cantidad recomendada de 3.</p><p style="margin:0;line-height:1.5;">Puede continuar si confirma la construcción del viaje.</p>', 						showCancelButton: true, 						confirmButtonText: 'Continuar', 						cancelButtonText: 'Cancelar', 						customClass: { 							popup: 'contenedor-modal', 							title: 'contener-modal-titulo', 							confirmButton: 'contener-modal-boton-confirmar', 							cancelButton: 'contener-modal-boton-cancelar' 						} 					}); 					if (!advertencia.isConfirmed) { 						return; 					} 				}  				const resumen = [ 					'Solicitudes: ' + seleccionadas.size, 					'Pacientes: ' + totalPacientes, 					'Personal: ' + personalSeleccionado.size, 					'Viáticos: ' + viaticosSeleccionados.size, 					'Vehículo: ' + obtenerTextoSeleccion(vehiculoNode, '-'), 					'Motorista: ' + obtenerTextoSeleccion(motoristaNode, '-') 				]; 				const confirmacion = await Swal.fire({ 					icon: 'question', 					title: 'Confirmar construcción', 					html: '<div style="text-align:left;line-height:1.55;">' + resumen.map(function (item) { return '<div>' + escapeHtml(item) + '</div>'; }).join('') + '<div style="margin-top:1rem;font-weight:700;">¿Desea construir el viaje con la información seleccionada?</div></div>', 					showCancelButton: true, 					confirmButtonText: 'Construir viaje', 					cancelButtonText: 'Cancelar', 					customClass: { 						popup: 'contenedor-modal', 						title: 'contener-modal-titulo', 						confirmButton: 'contener-modal-boton-confirmar', 						cancelButton: 'contener-modal-boton-cancelar' 					} 				}); 				if (!confirmacion.isConfirmed) { 					return; 				}  				const payload = { 					viaje_solicitud_ids: seleccionIds, 					vehiculo: vehiculoNode ? vehiculoNode.value : '', 					motorista: motoristaNode ? motoristaNode.value : '', 					tipo_viaje: tipoViajeNode ? tipoViajeNode.value : '', 					centro_costo: centroCostoNode ? centroCostoNode.value : '', 					personal_operativo_ids: personalHiddenNode ? personalHiddenNode.value : '[]', 					viaticos_json: viaticosHiddenNode ? viaticosHiddenNode.value : '[]' 				}; 				try { 					const response = await fetch(config.urlProgramacionConfirmar, { 						method: 'POST', 						headers: { 							'Content-Type': 'application/json', 							'X-Requested-With': 'XMLHttpRequest', 							'X-CSRFToken': getCookie('csrftoken') 						}, 						body: JSON.stringify(payload) 					}); 					const respuesta = await response.json().catch(function () { 						return {}; 					}); 					if (!response.ok) { 						throw new Error(respuesta.error || respuesta.message || respuesta.detail || 'No se pudo construir el viaje.'); 					} 					const numeroViaje = respuesta && respuesta.data ? respuesta.data.numero_viaje : '-'; 					await Swal.fire({ 						icon: 'success', 						title: 'Viaje construido', 						text: 'Viaje ' + numeroViaje + ' construido correctamente.' 					}); 					window.location.href = (config.tabsUrlBase || window.location.href) + '?tab=viaje_construccion'; 				} catch (error) { 					mostrarFeedback(error.message || 'No se pudo construir el viaje.'); 					await Swal.fire({ 						icon: 'error', 						title: 'No fue posible construir el viaje', 						text: error.message || 'No se pudo construir el viaje.' 					}); 				} 			}  			if (tableNode) { 				tableNode.addEventListener('change', function (event) { 					const checkbox = event.target.closest('[data-viaje-solicitud-checkbox]'); 					if (!checkbox) return; 					const row = checkbox.closest('tr'); 					const id = row ? row.dataset.viajeSolicitudId : ''; 					if (checkbox.checked) { 						agregarSolicitud(id); 					} else { 						quitarSolicitud(id); 					} 				}); 			}  			if (seleccionadasListNode) { 				seleccionadasListNode.addEventListener('click', function (event) { 					const removeButton = event.target.closest('[data-remove-viaje-solicitud]'); 					if (!removeButton) return; 					quitarSolicitud(removeButton.dataset.removeViajeSolicitud); 				}); 			}   			initSelectorPersonal(); 			initSelectsFormulario(); 			if (searchNode) { 				searchNode.addEventListener('input', aplicarBusquedaSolicitudes); 			}  			if (personalListNode) { 				personalListNode.addEventListener('click', function (event) { 					const button = event.target.closest('[data-remove-personal]'); 					if (!button) return; 					quitarPersonal(button.dataset.removePersonal); 				}); 			}  			if (viaticoAgregarNode) { 				viaticoAgregarNode.addEventListener('click', agregarViatico); 			}  			if (viaticosListNode) { 				viaticosListNode.addEventListener('click', function (event) { 					const button = event.target.closest('[data-remove-viatico]'); 					if (!button) return; 					quitarViatico(button.dataset.removeViatico); 				}); 			}  			if (confirmarNode) { 				confirmarNode.addEventListener('click', function () { 					void confirmarViaje(); 				}); 			}  			sincronizarPersonalSugerido(); 			renderSeleccionadas(); 			renderPersonal(); 			renderViaticos(); 			actualizarResumen(); 			aplicarBusquedaSolicitudes(); 		} 	} 	)();
;(function () {
const config = window.sgTransporteHospitalarioDashboard || {};
if (String(config.activeTab || '') !== 'ejecucion') {
return;
}

const tableSalida = document.getElementById('th-ejecucion-salida-table');
const tableEntrada = document.getElementById('th-ejecucion-entrada-table');
const modal = document.getElementById('th-ejecucion-modal');
const modalTitle = document.getElementById('th-ejecucion-modal-title');
const modalSubtitle = document.getElementById('th-ejecucion-modal-subtitle');
const modalContent = document.getElementById('th-ejecucion-modal-content');
const modalDecision = document.getElementById('th-ejecucion-modal-decision');
const guardarButton = document.getElementById('th-ejecucion-modal-guardar');

if (!modal || !modalContent) {
return;
}

let estadoModal = {
modo: 'ver',
row: null
};

function escapeHtml(value) {
return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
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

function parseDetalle(row) {
if (!row) return {};
try {
return JSON.parse(row.dataset.viajeDetalle || '{}') || {};
} catch (error) {
return {};
}
}

function getRowData(button) {
const row = button ? button.closest('tr') : null;
if (!row) return null;
return {
row: row,
id: String(row.dataset.viajeId || ''),
numero: String(row.dataset.viajeNumero || ''),
fecha: String(row.dataset.viajeFecha || ''),
vehiculo: String(row.dataset.viajeVehiculo || ''),
motorista: String(row.dataset.viajeMotorista || ''),
estado: String(row.dataset.viajeEstado || ''),
etapa: String(row.dataset.viajeEtapa || ''),
detalle: parseDetalle(row),
salidaRegistrada: String(row.dataset.viajeSalidaRegistrada || '') === '1',
entradaRegistrada: String(row.dataset.viajeEntradaRegistrada || '') === '1',
fechaSalidaInput: String(row.dataset.viajeFechaSalidaInput || ''),
fechaSalida: String(row.dataset.viajeFechaSalida || ''),
kilometrajeSalida: String(row.dataset.viajeKilometrajeSalida || ''),
precioLitroSalida: String(row.dataset.viajePrecioLitroSalida || ''),
litrosCargadosSalida: String(row.dataset.viajeLitrosCargadosSalida || ''),
totalCombustible: String(row.dataset.viajeTotalCombustible || ''),
observacionesSalida: String(row.dataset.viajeObservacionesSalida || ''),
fechaRetornoInput: String(row.dataset.viajeFechaRetornoInput || ''),
fechaRetorno: String(row.dataset.viajeFechaRetorno || ''),
kilometrajeRetorno: String(row.dataset.viajeKilometrajeRetorno || ''),
observacionesRetorno: String(row.dataset.viajeObservacionesRetorno || '')
};
}

function renderResumen(data) {
return [
'<div class="th-solicitud-modal__grid">',
'<section class="th-solicitud-modal__section">',
'<h5>Información del viaje</h5>',
'<div class="th-solicitud-modal__meta">',
'<div class="th-solicitud-modal__meta-item"><span>Número</span><strong>' + escapeHtml(data.numero || '-') + '</strong></div>',
'<div class="th-solicitud-modal__meta-item"><span>Fecha</span><strong>' + escapeHtml(data.fecha || '-') + '</strong></div>',
'<div class="th-solicitud-modal__meta-item"><span>Vehículo</span><strong>' + escapeHtml(data.vehiculo || '-') + '</strong></div>',
'<div class="th-solicitud-modal__meta-item"><span>Motorista</span><strong>' + escapeHtml(data.motorista || '-') + '</strong></div>',
'<div class="th-solicitud-modal__meta-item"><span>Etapa</span><strong>' + escapeHtml(data.etapa || '-') + '</strong></div>',
'</div>',
'</section>',
'</div>'
].join('');
}

function renderLineaMeta(label, value, extraClass) {
return '<div class="th-solicitud-modal__meta-item' + (extraClass ? ' ' + extraClass : '') + '">' + '<span>' + escapeHtml(label) + '</span>' + '<strong>' + escapeHtml(value || '-') + '</strong>' + '</div>';
}

function renderListaHtml(items, emptyText, renderItem) {
if (!items || !items.length) {
return '<div class="th-solicitud-modal__empty">' + escapeHtml(emptyText) + '</div>';
}
return '<div class="th-solicitud-modal__list">' + items.map(renderItem).join('') + '</div>';
}

function renderDetalleEjecucion(data) {
const detalle = data.detalle || {};
const infoGeneral = detalle.info_general || {};
const solicitudes = Array.isArray(detalle.solicitudes) ? detalle.solicitudes : [];
const pacientes = Array.isArray(detalle.pacientes) ? detalle.pacientes : [];
const personal = Array.isArray(detalle.personal_operativo) ? detalle.personal_operativo : [];
const motivos = Array.isArray(detalle.motivos) ? detalle.motivos : [];
const observaciones = Array.isArray(detalle.observaciones_viaje) ? detalle.observaciones_viaje : [];

return [
'<div class="th-solicitud-modal__hero">',
'<div class="th-solicitud-modal__hero-main">',
'<span class="th-solicitud-modal__eyebrow">Ejecución del viaje</span>',
'<h5>Viaje #' + escapeHtml(data.numero || '-') + '</h5>',
'<p>Vista completa de solo lectura con las solicitudes, pacientes, personal y observaciones consolidadas.</p>',
'</div>',
'<div class="th-solicitud-modal__hero-chips">',
'<span class="th-solicitud-modal__chip">' + escapeHtml(infoGeneral.estado_etiqueta || data.etapa || '-') + '</span>',
'<span class="th-solicitud-modal__chip">' + escapeHtml(infoGeneral.tipo_viaje || data.tipo_viaje || '-') + '</span>',
'<span class="th-solicitud-modal__chip">' + escapeHtml(infoGeneral.ambulancia || data.vehiculo || '-') + '</span>',
'<span class="th-solicitud-modal__chip">' + escapeHtml(infoGeneral.motorista || data.motorista || '-') + '</span>',
'</div>',
'</div>',
'<div class="th-solicitud-modal__grid">',
'<section class="th-solicitud-modal__section">',
'<h5>Información general</h5>',
'<div class="th-solicitud-modal__meta">',
renderLineaMeta('Número', infoGeneral.numero || data.numero || '-'),
renderLineaMeta('Estado', infoGeneral.estado_etiqueta || data.etapa || data.estado_etiqueta || '-'),
renderLineaMeta('Tipo de viaje', infoGeneral.tipo_viaje || data.tipo_viaje || '-'),
renderLineaMeta('Vehículo', infoGeneral.ambulancia || data.vehiculo || '-'),
renderLineaMeta('Motorista', infoGeneral.motorista || data.motorista || '-'),
'</div>',
'</section>',
'<section class="th-solicitud-modal__section">',
'<h5>Salida</h5>',
'<div class="th-solicitud-modal__meta">',
renderLineaMeta('Fecha/hora de salida', data.fechaSalida || '-'),
renderLineaMeta('Kilometraje inicial', data.kilometrajeSalida || '-'),
renderLineaMeta('Precio por litro', data.precioLitroSalida || '-'),
renderLineaMeta('Litros cargados', data.litrosCargadosSalida || '-'),
renderLineaMeta('Total combustible', data.totalCombustible || '-'),
renderLineaMeta('Observaciones', data.observacionesSalida || '-', 'th-solicitud-modal__meta-item--wide'),
'</div>',
'</section>',
'<section class="th-solicitud-modal__section">',
'<h5>Retorno</h5>',
'<div class="th-solicitud-modal__meta">',
renderLineaMeta('Fecha/hora de retorno', data.fechaRetorno || '-'),
renderLineaMeta('Kilometraje final', data.kilometrajeRetorno || '-'),
renderLineaMeta('Observaciones', data.observacionesRetorno || '-', 'th-solicitud-modal__meta-item--wide'),
'</div>',
'</section>',
'<section class="th-solicitud-modal__section">',
'<h5>Solicitudes consolidadas</h5>',
renderListaHtml(solicitudes, 'No hay solicitudes consolidadas en esta ejecución.', function (item) {
return [
'<article class="th-solicitud-modal__item">',
'<strong>Solicitud #' + escapeHtml(item.numero || '-') + '</strong>',
'<div>Punto: ' + escapeHtml(item.punto || '-') + '</div>',
'<div>Prioridad: ' + escapeHtml(item.prioridad || '-') + '</div>',
'<div class="th-solicitud-modal__focus">' + escapeHtml(Array.isArray(item.motivos) && item.motivos.length ? item.motivos.join(' · ') : 'Sin motivo') + '</div>',
'</article>'
].join('');
}),
'</section>',
'<section class="th-solicitud-modal__section">',
'<h5>Pacientes</h5>',
renderListaHtml(pacientes, 'No hay pacientes consolidados.', function (item) {
return '<article class="th-solicitud-modal__item"><strong>' + escapeHtml(item.paciente || '-') + '</strong><div>' + escapeHtml(item.identidad || '-') + '</div><small>' + escapeHtml(item.solicitud || '-') + '</small></article>';
}),
'</section>',
'<section class="th-solicitud-modal__section">',
'<h5>Personal operativo</h5>',
renderListaHtml(personal, 'No hay personal operativo registrado.', function (item) {
return '<article class="th-solicitud-modal__item"><strong>' + escapeHtml(item.nombre || '-') + '</strong><div>' + escapeHtml(item.cargo || '-') + '</div><small>' + escapeHtml(item.unidad || '-') + ' - ' + escapeHtml(item.participacion || '-') + '</small></article>';
}),
'</section>',
'<section class="th-solicitud-modal__section">',
'<h5>Motivos consolidados</h5>',
renderListaHtml(motivos, 'No hay motivos consolidados.', function (item) {
const motivoTexto = Array.isArray(item.items) ? item.items.join(' · ') : '';
return '<article class="th-solicitud-modal__item"><strong>Solicitud #' + escapeHtml(item.numero || '-') + '</strong><div>' + escapeHtml(motivoTexto || 'Sin motivo') + '</div></article>';
}),
'</section>',
'<section class="th-solicitud-modal__section">',
'<h5>Observaciones</h5>',
renderListaHtml(observaciones, 'No hay observaciones registradas.', function (item) {
return '<article class="th-solicitud-modal__item"><strong>' + escapeHtml(item.etapa || '-') + '</strong><div>' + escapeHtml(item.texto || '-') + '</div></article>';
}),
'</section>',
'</div>'
].join('');
}

function renderSalidaForm(data) {
return [
'<form id="th-ejecucion-form" class="th-viaje-programacion__grid">',
'<input type="hidden" name="viaje_id" value="' + escapeHtml(data.id) + '">',
'<input type="hidden" name="modo" value="salida">',
'<div class="th-viaje-programacion__field"><span>Fecha de salida</span><input type="datetime-local" name="fecha_salida" class="th-input" value="' + escapeHtml(data.fechaSalidaInput || '') + '"></div>',
'<div class="th-viaje-programacion__field"><span>Kilometraje de salida</span><input type="number" name="kilometraje_salida" class="th-input" min="0" step="0.01" value="' + escapeHtml(data.kilometrajeSalida || '') + '"></div>',
'<div class="th-viaje-programacion__field"><span>Precio por litro</span><input type="number" name="precio_litro_salida" class="th-input" min="0" step="0.01" value="' + escapeHtml(data.precioLitroSalida || '') + '" oninput="window.sgThEjecucion && window.sgThEjecucion.actualizarTotalCombustibleSalida && window.sgThEjecucion.actualizarTotalCombustibleSalida(this.form)" onchange="window.sgThEjecucion && window.sgThEjecucion.actualizarTotalCombustibleSalida && window.sgThEjecucion.actualizarTotalCombustibleSalida(this.form)"></div>',
'<div class="th-viaje-programacion__field"><span>Litros cargados</span><input type="number" name="litros_cargados_salida" class="th-input" min="0" step="0.01" value="' + escapeHtml(data.litrosCargadosSalida || '') + '" oninput="window.sgThEjecucion && window.sgThEjecucion.actualizarTotalCombustibleSalida && window.sgThEjecucion.actualizarTotalCombustibleSalida(this.form)" onchange="window.sgThEjecucion && window.sgThEjecucion.actualizarTotalCombustibleSalida && window.sgThEjecucion.actualizarTotalCombustibleSalida(this.form)"></div>',
'<div class="th-viaje-programacion__field th-span-12"><span>Total combustible</span><input type="number" name="total_combustible" class="th-input" readonly tabindex="-1" value="' + escapeHtml(data.totalCombustible || '') + '"></div>',
'<div class="th-viaje-programacion__field th-span-12"><span>Observaciones de salida</span><textarea name="observaciones_salida" class="th-input" rows="2">' + escapeHtml(data.observacionesSalida || '') + '</textarea></div>',
'</form>'
].join('');
}

function actualizarTotalCombustible(form) {
const precioInput = form ? form.querySelector('[name="precio_litro_salida"]') : null;
const litrosInput = form ? form.querySelector('[name="litros_cargados_salida"]') : null;
const totalInput = form ? form.querySelector('[name="total_combustible"]') : null;
if (!precioInput || !litrosInput || !totalInput) {
return;
}
const precio = Number(String(precioInput.value || '').replace(',', '.'));
const litros = Number(String(litrosInput.value || '').replace(',', '.'));
if (Number.isFinite(precio) && Number.isFinite(litros) && precio >= 0 && litros >= 0) {
totalInput.value = (precio * litros).toFixed(2);
return;
}
totalInput.value = '';
}

function bindTotalCombustibleSalida() {
const form = document.getElementById('th-ejecucion-form');
if (!form) {
return;
}
const precioInput = form.querySelector('[name="precio_litro_salida"]');
const litrosInput = form.querySelector('[name="litros_cargados_salida"]');
if (!precioInput || !litrosInput) {
return;
}
const refresh = function () {
actualizarTotalCombustible(form);
};
precioInput.addEventListener('input', refresh);
litrosInput.addEventListener('input', refresh);
actualizarTotalCombustible(form);
}

function renderEntradaForm(data) {
return [
'<form id="th-ejecucion-form" class="th-viaje-programacion__grid">',
'<input type="hidden" name="viaje_id" value="' + escapeHtml(data.id) + '">',
'<input type="hidden" name="modo" value="entrada">',
'<div class="th-viaje-programacion__field"><span>Fecha de retorno</span><input type="datetime-local" name="fecha_retorno" class="th-input" value="' + escapeHtml(data.fechaRetornoInput || '') + '"></div>',
'<div class="th-viaje-programacion__field"><span>Kilometraje de retorno</span><input type="number" name="kilometraje_retorno" class="th-input" min="0" step="0.01" value="' + escapeHtml(data.kilometrajeRetorno || '') + '"></div>',
'<div class="th-viaje-programacion__field th-span-12"><span>Observaciones de retorno</span><textarea name="observaciones_retorno" class="th-input" rows="2">' + escapeHtml(data.observacionesRetorno || '') + '</textarea></div>',
'</form>'
].join('');
}

function renderModal(data, modo) {
modalContent.innerHTML = modo === 'ver' ? renderDetalleEjecucion(data) : renderResumen(data) + (modo === 'salida' ? renderSalidaForm(data) : modo === 'entrada' ? renderEntradaForm(data) : '');
if (modalTitle) {
modalTitle.textContent = modo === 'salida' ? 'Registrar salida' : modo === 'entrada' ? 'Registrar entrada' : 'Detalle del viaje';
}
if (modalSubtitle) {
modalSubtitle.textContent = modo === 'salida' ? 'Registro operativo de salida' : modo === 'entrada' ? 'Registro operativo de entrada' : 'Detalle completo del viaje';
}
if (modalDecision) {
modalDecision.textContent = modo === 'salida' ? 'Complete los datos de salida y guarde.' : modo === 'entrada' ? 'Complete los datos de entrada y guarde.' : 'Vista de solo lectura del viaje seleccionado.';
}
if (guardarButton) {
guardarButton.hidden = modo === 'ver';
}
if (modo === 'salida') {
bindTotalCombustibleSalida();
}
}

function abrirModal(data, modo) {
if (!data || !data.row) return;
estadoModal = { modo: modo, row: data.row };
renderModal(data, modo);
modal.classList.add('is-open');
modal.setAttribute('aria-hidden', 'false');
document.body.classList.add('th-modal-open');
}

function cerrarModal() {
modal.classList.remove('is-open');
modal.setAttribute('aria-hidden', 'true');
document.body.classList.remove('th-modal-open');
modalContent.innerHTML = '<div class="th-solicitud-modal__empty">Seleccione un viaje para ver o registrar su ejecución.</div>';
estadoModal = { modo: 'ver', row: null };
}

async function requestJson(payload) {
const response = await fetch(config.urlEjecucionGuardar, {
method: 'POST',
headers: {
'Content-Type': 'application/json',
'X-Requested-With': 'XMLHttpRequest',
'X-CSRFToken': getCookie('csrftoken')
},
body: JSON.stringify(payload)
});
const data = await response.json().catch(function () { return {}; });
if (!response.ok) {
throw new Error(data.error || data.message || data.detail || 'No se pudo guardar la ejecución.');
}
return data;
}

function bindTable(tableNode, modo) {
if (!tableNode) return;
tableNode.addEventListener('click', function (event) {
const viewButton = event.target.closest('[data-ejecucion-ver]');
const salidaButton = event.target.closest('[data-ejecucion-salida]');
const entradaButton = event.target.closest('[data-ejecucion-entrada]');
if (viewButton || salidaButton || entradaButton) {
event.preventDefault();
const data = getRowData(viewButton || salidaButton || entradaButton);
if (!data) return;
abrirModal(data, viewButton ? 'ver' : salidaButton ? 'salida' : 'entrada');
}
});
}

bindTable(tableSalida, 'salida');
bindTable(tableEntrada, 'entrada');

window.sgThEjecucion = {
actualizarTotalCombustibleSalida: function (form) {
actualizarTotalCombustible(form || document.getElementById('th-ejecucion-form'));
},
ver: function (button, event) {
if (event) {
event.preventDefault();
event.stopPropagation();
}
const data = getRowData(button);
if (data) {
abrirModal(data, 'ver');
}
return false;
},
marcarSalida: function (button, event) {
if (event) {
event.preventDefault();
event.stopPropagation();
}
const data = getRowData(button);
if (data) {
abrirModal(data, 'salida');
}
return false;
},
marcarEntrada: function (button, event) {
if (event) {
event.preventDefault();
event.stopPropagation();
}
const data = getRowData(button);
if (data) {
abrirModal(data, 'entrada');
}
return false;
},
cerrarModal: function (button, event) {
if (event) {
event.preventDefault();
event.stopPropagation();
}
cerrarModal();
return false;
},
guardarModal: async function (button, event) {
if (event) {
event.preventDefault();
event.stopPropagation();
}
const form = document.getElementById('th-ejecucion-form');
if (!form || !estadoModal.row) {
return false;
}
if (String(form.querySelector('[name="modo"]').value || '') === 'salida') {
actualizarTotalCombustible(form);
}
const payload = {
viaje_id: Number(form.querySelector('[name="viaje_id"]').value || 0),
modo: String(form.querySelector('[name="modo"]').value || '')
};
Array.from(form.elements).forEach(function (element) {
if (!element.name || element.name === 'viaje_id' || element.name === 'modo') {
return;
}
if (element.type === 'checkbox') {
payload[element.name] = element.checked;
return;
}
payload[element.name] = element.value;
});
try {
if (button) button.disabled = true;
await requestJson(payload);
window.location.reload();
} catch (error) {
if (window.Swal) {
await Swal.fire({ icon: 'error', title: 'No fue posible guardar la ejecución', text: error.message || 'No se pudo guardar.' });
} else {
alert(error.message || 'No se pudo guardar.');
}
} finally {
if (button) button.disabled = false;
}
return false;
}
};

modal.querySelectorAll('[data-modal-close]').forEach(function (node) {
node.addEventListener('click', function (event) {
event.preventDefault();
cerrarModal();
});
});
})();