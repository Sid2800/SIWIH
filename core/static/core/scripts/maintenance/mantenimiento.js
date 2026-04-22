$(document).ready(function () {
    
    const API_URLS = {
        reclasificarRN: urls["reclasificarRN"]
    };

    const usuarios = JSON.parse(
        document.getElementById('usuarios-data').textContent
    );

    //text de busqqueda
    const ReclasificarRN = document.getElementById('cantidad_afectados_rn');
    const BtnReclasificarRN = document.getElementById('btn_reclasificar_rn');

    // text cantidad de usuarios
    const labelCantidadusuarios = document.getElementById('cantidad_usuarios');
    const btnDefinirImagenesUsuarios = document.getElementById('btn_definir_imagen_usuario');


    
    if (usuarios){
        labelCantidadusuarios.textContent  =  usuarios.length;
    }
    


    async function traer_RN_candidatos_HIJO(ejecutar) {
        const csrfToken = window.CSRF_TOKEN;

        try {
            const response = await fetch(API_URLS.reclasificarRN, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({ ejecutar })
            });

            const data = await response.json();

            if (!response.ok) {
                if (data.error) {
                    toastr.error(data.error, "Error");
                } else if (data.errors) {
                    Object.entries(data.errors).forEach(([campo, mensaje]) => {
                        toastr.error(mensaje, `Error en: ${campo}`);
                    });
                } else {
                    toastr.error("Ocurrió un error inesperado.");
                }
                return;
            }

            if (data.success) {
                if (data.actualizacion){
                    toastr.success(`Se actualizaron ${data.cantidad} registros`);
                    setTimeout(() => {
                        location.reload();
                    }, 1500);
                }else
                {
                    ReclasificarRN.textContent  =  data.cantidad;
                    // Deshabilitar o habilitar el botón según la cantidad
                    BtnReclasificarRN.disabled = (data.cantidad === 0);

                }

            } else {
                toastr.error(data.error || "Ocurrió un error durante el proceso.");
            }
        } catch (error) {
            console.error("Error:", error);
            toastr.error("Hubo un error inesperado al registrar encontrar registros.");
        }
    }

    BtnReclasificarRN.addEventListener('click', async function (){
        const resultado = await confirmarAccion('¿Está seguro?', `Realmente desea reclasificar ${ReclasificarRN.textContent} Recien Nacidos`);
        if (resultado){
            BtnReclasificarRN.disabled = true;
            await traer_RN_candidatos_HIJO(true);
            BtnReclasificarRN.disabled = false;
        }
        
    });

    

    btnDefinirImagenesUsuarios.addEventListener('click', async function () {
        ModalGaleriaUsuario.open(
            {
            titulo: "Actualizar imagenes de usuarios",
            usuarios: usuarios
            }
        );
    });





    traer_RN_candidatos_HIJO();




    
});




