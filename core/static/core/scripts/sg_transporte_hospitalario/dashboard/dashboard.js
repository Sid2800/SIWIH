(function () {
	const config = window.sgTransporteHospitalarioDashboard || {};
	if (config.activeTab !== 'solicitud') {
		return;
	}

	if (!window.jQuery || !jQuery.fn.DataTable) {
		return;
	}

	const tabla = jQuery('#th-solicitudes-activas-table').DataTable({
		order: [[1, 'desc']],
		language: {
			emptyTable: config.emptyTable || 'No hay registros disponibles.'
		}
	});

	const criterioBusqueda = document.getElementById('th-solicitud-criterio');
	const inputBusqueda = document.getElementById('th-solicitud-busqueda');
	const btnBuscar = document.getElementById('th-solicitud-buscar');
	const btnLimpiar = document.getElementById('th-solicitud-limpiar');
	const filtroEstado = document.getElementById('th-filtro-estado');
	const filtroArea = document.getElementById('th-filtro-area');
	const filtroTipo = document.getElementById('th-filtro-tipo');

	function aplicarBusquedaSolicitud() {
		if (!criterioBusqueda || !inputBusqueda) {
			return;
		}

		const criterio = Number(criterioBusqueda.value || 0);
		const valor = (inputBusqueda.value || '').trim();

		tabla.search('');
		tabla.columns().search('');
		tabla.column(criterio).search(valor).draw();
	}

	function limpiarBusquedaSolicitud() {
		if (criterioBusqueda) {
			criterioBusqueda.value = '0';
		}
		if (inputBusqueda) {
			inputBusqueda.value = '';
		}
		if (filtroEstado) {
			filtroEstado.value = '';
		}
		if (filtroArea) {
			filtroArea.value = '';
		}
		if (filtroTipo) {
			filtroTipo.value = '';
		}

		tabla.search('');
		tabla.columns().search('');
		tabla.order([[1, 'desc']]);
		tabla.page('first').draw();
	}

	if (btnBuscar) {
		btnBuscar.addEventListener('click', aplicarBusquedaSolicitud);
	}

	if (btnLimpiar) {
		btnLimpiar.addEventListener('click', limpiarBusquedaSolicitud);
	}

	if (inputBusqueda) {
		inputBusqueda.addEventListener('keydown', function (event) {
			if (event.key === 'Enter') {
				event.preventDefault();
				aplicarBusquedaSolicitud();
			}
		});
	}

	function aplicarFiltro(selectId, columnIndex) {
		const node = document.getElementById(selectId);
		if (!node) return;
		node.addEventListener('change', function () {
			const value = node.value || '';
			tabla.column(columnIndex).search(value).draw();
		});
	}

	aplicarFiltro('th-filtro-estado', 5);
	aplicarFiltro('th-filtro-area', 2);
	aplicarFiltro('th-filtro-tipo', 3);
})();
