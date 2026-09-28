// Detalle de una procedencia en un cuadro de dialogo.
//
// La tarjeta muestra solo el nombre: los siete datos de una procedencia no
// caben en una tarjeta legible y tampoco se consultan a diario. Un clic los
// abre aqui y el doble clic lleva directo a editar.
//
// Los datos vienen en los atributos de la propia tarjeta, asi que abrir el
// cuadro no consulta al servidor.
document.addEventListener('DOMContentLoaded', function () {
    const dialogo = document.getElementById('dialogo_procedencia');
    const tarjetas = document.querySelectorAll('.equipos-procedencias__tarjeta');

    if (!dialogo || !tarjetas.length) {
        return;
    }

    const titulo = document.getElementById('dialogo_procedencia_nombre');
    const datos = document.getElementById('dialogo_procedencia_datos');
    const cerrar = document.getElementById('dialogo_procedencia_cerrar');
    const editar = document.getElementById('dialogo_procedencia_editar');
    const formEstado = document.getElementById('dialogo_procedencia_estado');
    const textoEstado = document.getElementById('dialogo_procedencia_estado_texto');

    // El doble clic tambien dispara dos clics sueltos. Se espera este margen
    // antes de abrir el cuadro: si llega el segundo clic, se cancela y manda
    // la edicion. 250ms es lo que tarda un doble clic normal.
    const ESPERA_DOBLE_CLIC = 250;
    let temporizador = null;

    function texto(valor) {
        return (valor || '').trim() || 'No indicado';
    }

    function abrir(tarjeta) {
        const d = tarjeta.dataset;

        titulo.textContent = d.nombre;

        const filas = [
            ['Tipo', d.tipo],
            ['RTN', texto(d.rtn)],
            ['Teléfono', texto(d.telefono)],
            ['Teléfono alterno', texto(d.telefonoAlterno)],
            ['Persona de contacto', texto(d.contacto)],
            ['Correo', texto(d.correo)],
            ['Equipos registrados', d.equipos],
            ['Estado', d.activo === '1' ? 'Activa' : 'Inactiva'],
        ];

        datos.replaceChildren();

        filas.forEach(function ([etiqueta, valor]) {
            const fila = document.createElement('div');
            const dt = document.createElement('dt');
            const dd = document.createElement('dd');

            dt.textContent = etiqueta;
            dd.textContent = valor;
            fila.append(dt, dd);
            datos.append(fila);
        });

        if (editar) {
            editar.href = d.urlEditar || '#';
            editar.hidden = !d.urlEditar;
        }

        if (formEstado) {
            // La ruta se resuelve en la plantilla con un cero y aqui se
            // sustituye por el identificador real.
            const plantilla = dialogo.dataset.urlEstado || '';
            formEstado.action = plantilla.replace(/\/0\//, `/${d.id}/`);
            formEstado.hidden = !plantilla;

            if (textoEstado) {
                textoEstado.textContent = d.activo === '1'
                    ? 'Desactivar'
                    : 'Reactivar';
            }
        }

        dialogo.showModal();
    }

    tarjetas.forEach(function (tarjeta) {
        tarjeta.addEventListener('click', function () {
            if (temporizador) {
                return;
            }

            temporizador = window.setTimeout(function () {
                temporizador = null;
                abrir(tarjeta);
            }, ESPERA_DOBLE_CLIC);
        });

        tarjeta.addEventListener('dblclick', function () {
            window.clearTimeout(temporizador);
            temporizador = null;

            if (tarjeta.dataset.urlEditar) {
                window.location.href = tarjeta.dataset.urlEditar;
            }
        });
    });

    if (cerrar) {
        cerrar.addEventListener('click', function () {
            dialogo.close();
        });
    }

    // Pulsar el fondo cierra, que es lo que espera cualquiera. El <dialog>
    // recibe el clic tanto en su caja como en el fondo, asi que se compara
    // con el rectangulo para distinguirlos.
    dialogo.addEventListener('click', function (evento) {
        const caja = dialogo.getBoundingClientRect();
        const dentro = (
            evento.clientX >= caja.left
            && evento.clientX <= caja.right
            && evento.clientY >= caja.top
            && evento.clientY <= caja.bottom
        );

        if (!dentro) {
            dialogo.close();
        }
    });
});
