let currentPage = 1;
let totalItems = 0;
let itemsPerPage = 50;
let currentSort = 'artist';

document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('library-container')) {
        // Initialize library view
        initLibraryView();
        
        // Set up event listeners
        setupLibraryEventListeners();
    }
});

function initLibraryView() {
    // Load library items
    loadLibraryItems();
    
    // Load artists for the filter dropdown
    loadArtists();
}

function setupLibraryEventListeners() {
    // Pagination controls
    document.getElementById('prev-page').addEventListener('click', function() {
        if (currentPage > 1) {
            currentPage--;
            loadLibraryItems();
        }
    });
    
    document.getElementById('next-page').addEventListener('click', function() {
        const maxPage = Math.ceil(totalItems / itemsPerPage);
        if (currentPage < maxPage) {
            currentPage++;
            loadLibraryItems();
        }
    });
    
    // Search form
    document.getElementById('search-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const searchQuery = document.getElementById('search-input').value.trim();
        if (searchQuery) {
            searchLibrary(searchQuery);
        } else {
            loadLibraryItems();
        }
    });
    
    // Artist filter change
    document.getElementById('artist-filter').addEventListener('change', function() {
        const selectedArtist = this.value;
        if (selectedArtist) {
            loadAlbumsByArtist(selectedArtist);
        }
    });
    
    // Sort options
    document.querySelectorAll('.sort-option').forEach(option => {
        option.addEventListener('click', function(e) {
            e.preventDefault();
            currentSort = this.getAttribute('data-sort');
            document.getElementById('current-sort').textContent = this.textContent;
            currentPage = 1;
            loadLibraryItems();
        });
    });
    
    // Items per page change
    document.getElementById('items-per-page').addEventListener('change', function() {
        itemsPerPage = parseInt(this.value);
        currentPage = 1;
        loadLibraryItems();
    });
}

function loadLibraryItems() {
    const libraryTable = document.getElementById('library-table');
    const loadingIndicator = document.getElementById('loading-indicator');
    const paginationInfo = document.getElementById('pagination-info');
    
    // Show loading indicator
    loadingIndicator.classList.remove('d-none');
    libraryTable.classList.add('d-none');
    
    // Make API request to get library items
    fetch(`/api/library?page=${currentPage}&limit=${itemsPerPage}&sort=${currentSort}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load library items');
            }
            return response.json();
        })
        .then(data => {
            // Update total items count
            totalItems = data.total;
            
            // Render items in the table
            renderLibraryItems(data.items);
            
            // Update pagination info
            const startItem = (currentPage - 1) * itemsPerPage + 1;
            const endItem = Math.min(startItem + itemsPerPage - 1, totalItems);
            paginationInfo.textContent = `Showing ${startItem}-${endItem} of ${totalItems} items`;
            
            // Update pagination buttons state
            document.getElementById('prev-page').disabled = currentPage === 1;
            document.getElementById('next-page').disabled = currentPage >= Math.ceil(totalItems / itemsPerPage);
            
            // Hide loading indicator
            loadingIndicator.classList.add('d-none');
            libraryTable.classList.remove('d-none');
        })
        .catch(error => {
            console.error('Error loading library:', error);
            showError('Failed to load library: ' + error.message);
            loadingIndicator.classList.add('d-none');
        });
}

function renderLibraryItems(items) {
    const tableBody = document.getElementById('library-table-body');
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    if (items.length === 0) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `<td colspan="6" class="text-center">No items found</td>`;
        tableBody.appendChild(emptyRow);
        return;
    }
    
    // Create a row for each item
    items.forEach(item => {
        const row = document.createElement('tr');
        row.setAttribute('data-item-id', item.id);
        row.style.cursor = 'pointer';
        
        row.innerHTML = `
            <td>${item.title || 'Unknown'}</td>
            <td>${item.artist || 'Unknown'}</td>
            <td>${item.album || 'Unknown'}</td>
            <td>${item.year || '-'}</td>
            <td>${item.length_formatted || '-'}</td>
            <td>${item.format || '-'}</td>
        `;
        
        // Add click event to show item details
        row.addEventListener('click', function() {
            showItemDetails(item.id);
        });
        
        tableBody.appendChild(row);
    });
}

function showItemDetails(itemId) {
    const detailsModal = new bootstrap.Modal(document.getElementById('item-details-modal'));
    const modalBody = document.getElementById('item-details-content');
    const modalTitle = document.getElementById('item-details-title');
    const modalLoading = document.getElementById('item-details-loading');
    
    // Show loading state
    modalTitle.textContent = 'Loading...';
    modalBody.innerHTML = '';
    modalLoading.classList.remove('d-none');
    detailsModal.show();
    
    // Fetch item details
    fetch(`/api/item/${itemId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load item details');
            }
            return response.json();
        })
        .then(item => {
            // Hide loading indicator
            modalLoading.classList.add('d-none');
            
            // Update modal title
            modalTitle.textContent = `${item.title} - ${item.artist}`;
            
            // Render item details
            let detailsHtml = '<div class="row">';
            
            // Album art column (if available)
            detailsHtml += '<div class="col-md-4 mb-3">';
            detailsHtml += `<div id="album-art-container" class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>`;
            detailsHtml += '</div>';
            
            // Item details column
            detailsHtml += '<div class="col-md-8">';
            detailsHtml += '<table class="table table-sm">';
            detailsHtml += `<tr><th>Title</th><td>${item.title || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Artist</th><td>${item.artist || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Album</th><td>${item.album || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Album Artist</th><td>${item.albumartist || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Year</th><td>${item.year || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Track</th><td>${item.track || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Genre</th><td>${item.genre || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Length</th><td>${item.length_formatted || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Format</th><td>${item.format || '-'}</td></tr>`;
            detailsHtml += `<tr><th>Bitrate</th><td>${item.bitrate ? item.bitrate + ' kbps' : '-'}</td></tr>`;
            detailsHtml += `<tr><th>Path</th><td><small>${item.path || '-'}</small></td></tr>`;
            detailsHtml += '</table>';
            detailsHtml += '</div>';
            
            detailsHtml += '</div>';
            
            modalBody.innerHTML = detailsHtml;
            
            // Load album art
            loadAlbumArt(itemId);
        })
        .catch(error => {
            console.error('Error loading item details:', error);
            modalLoading.classList.add('d-none');
            modalBody.innerHTML = `<div class="alert alert-danger">Failed to load item details: ${error.message}</div>`;
        });
}

function loadAlbumArt(itemId) {
    const artContainer = document.getElementById('album-art-container');
    
    fetch(`/api/albumart/${itemId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load album art');
            }
            return response.json();
        })
        .then(data => {
            if (data.albumArt) {
                // Create and display the image
                const img = document.createElement('img');
                img.src = `data:image/jpeg;base64,${data.albumArt}`;
                img.className = 'img-fluid rounded';
                img.alt = 'Album Cover';
                artContainer.innerHTML = '';
                artContainer.appendChild(img);
            } else {
                // Show placeholder
                artContainer.innerHTML = '<div class="text-center p-5 bg-light rounded"><i class="fas fa-music fa-4x text-muted"></i><p class="mt-3 text-muted">No album art available</p></div>';
            }
        })
        .catch(error => {
            console.error('Error loading album art:', error);
            artContainer.innerHTML = '<div class="text-center p-5 bg-light rounded"><i class="fas fa-music fa-4x text-muted"></i><p class="mt-3 text-muted">No album art available</p></div>';
        });
}

function searchLibrary(query) {
    const libraryTable = document.getElementById('library-table');
    const loadingIndicator = document.getElementById('loading-indicator');
    const paginationInfo = document.getElementById('pagination-info');
    
    // Show loading indicator
    loadingIndicator.classList.remove('d-none');
    libraryTable.classList.add('d-none');
    
    // Make API request to search the library
    fetch(`/api/search?query=${encodeURIComponent(query)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to search library');
            }
            return response.json();
        })
        .then(data => {
            // Render search results
            renderLibraryItems(data.results);
            
            // Update pagination info
            paginationInfo.textContent = `Found ${data.results.length} items matching "${query}"`;
            
            // Hide pagination buttons during search
            document.getElementById('pagination-controls').classList.add('d-none');
            
            // Show clear search button
            const clearButton = document.getElementById('clear-search');
            clearButton.classList.remove('d-none');
            clearButton.addEventListener('click', function() {
                document.getElementById('search-input').value = '';
                document.getElementById('pagination-controls').classList.remove('d-none');
                this.classList.add('d-none');
                currentPage = 1;
                loadLibraryItems();
            });
            
            // Hide loading indicator
            loadingIndicator.classList.add('d-none');
            libraryTable.classList.remove('d-none');
        })
        .catch(error => {
            console.error('Error searching library:', error);
            showError('Failed to search library: ' + error.message);
            loadingIndicator.classList.add('d-none');
        });
}

function loadArtists() {
    const artistFilter = document.getElementById('artist-filter');
    
    fetch('/api/artists')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load artists');
            }
            return response.json();
        })
        .then(data => {
            // Clear existing options but keep the default one
            artistFilter.innerHTML = '<option value="">All Artists</option>';
            
            // Add artist options
            data.artists.forEach(artist => {
                const option = document.createElement('option');
                option.value = artist;
                option.textContent = artist;
                artistFilter.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error loading artists:', error);
            showError('Failed to load artists: ' + error.message);
        });
}

function loadAlbumsByArtist(artist) {
    const libraryTable = document.getElementById('library-table');
    const loadingIndicator = document.getElementById('loading-indicator');
    const paginationInfo = document.getElementById('pagination-info');
    
    // Show loading indicator
    loadingIndicator.classList.remove('d-none');
    libraryTable.classList.add('d-none');
    
    // Make API request to get albums by artist
    fetch(`/api/albums?artist=${encodeURIComponent(artist)}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load albums');
            }
            return response.json();
        })
        .then(data => {
            const tableBody = document.getElementById('library-table-body');
            
            // Clear existing rows
            tableBody.innerHTML = '';
            
            if (data.albums.length === 0) {
                const emptyRow = document.createElement('tr');
                emptyRow.innerHTML = `<td colspan="6" class="text-center">No albums found for artist "${artist}"</td>`;
                tableBody.appendChild(emptyRow);
            } else {
                // Create a row for each album
                data.albums.forEach(album => {
                    const row = document.createElement('tr');
                    row.style.cursor = 'pointer';
                    
                    row.innerHTML = `
                        <td colspan="2">${album.album || 'Unknown'}</td>
                        <td>${album.artist || artist}</td>
                        <td>${album.year || '-'}</td>
                        <td colspan="2">${album.albumartist || artist}</td>
                    `;
                    
                    // Add click event to filter by album
                    row.addEventListener('click', function() {
                        const query = `album:${album.album} artist:${artist}`;
                        document.getElementById('search-input').value = query;
                        searchLibrary(query);
                    });
                    
                    tableBody.appendChild(row);
                });
            }
            
            // Update pagination info
            paginationInfo.textContent = `Showing ${data.albums.length} albums for artist "${artist}"`;
            
            // Hide pagination buttons during filter
            document.getElementById('pagination-controls').classList.add('d-none');
            
            // Show clear filter button
            const clearButton = document.getElementById('clear-search');
            clearButton.classList.remove('d-none');
            clearButton.addEventListener('click', function() {
                document.getElementById('artist-filter').value = '';
                document.getElementById('pagination-controls').classList.remove('d-none');
                this.classList.add('d-none');
                currentPage = 1;
                loadLibraryItems();
            });
            
            // Hide loading indicator
            loadingIndicator.classList.add('d-none');
            libraryTable.classList.remove('d-none');
        })
        .catch(error => {
            console.error('Error loading albums:', error);
            showError('Failed to load albums: ' + error.message);
            loadingIndicator.classList.add('d-none');
        });
}
