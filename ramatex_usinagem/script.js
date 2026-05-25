document.addEventListener('DOMContentLoaded', () => {
    const slides = document.querySelector('.slides');
    const slideCount = document.querySelectorAll('.slide').length;
    const prevButton = document.querySelector('.prev');
    const nextButton = document.querySelector('.next');
    let currentIndex = 0;

    function updateCarousel() {
        const offset = -currentIndex * 100; // Move os slides
        slides.style.transform = `translateX(${offset}%)`;
    }

    nextButton.addEventListener('click', () => {
        currentIndex = (currentIndex + 1) % slideCount;
        updateCarousel();
    });

    prevButton.addEventListener('click', () => {
        currentIndex = (currentIndex - 1 + slideCount) % slideCount;
        updateCarousel();
    });
});

// Máscara Automática para o Telefone na página de contato
document.addEventListener('DOMContentLoaded', () => {
    const inputTelefone = document.getElementById('telefone');
    
    if (inputTelefone) {
        inputTelefone.addEventListener('input', (e) => {
            let limparValor = e.target.value.replace(/\D/g, ""); // Remove tudo que não for número
            let valorFormatado = "";

            if (limparValor.length > 0) {
                valorFormatado = `(${limparValor.substring(0, 2)}`;
            }
            if (limparValor.length > 2) {
                valorFormatado += `) ${limparValor.substring(2, 7)}`;
            }
            if (limparValor.length > 7) {
                valorFormatado += `-${limparValor.substring(7, 11)}`;
            }
            
            e.target.value = valorFormatado;
        });
    }
});