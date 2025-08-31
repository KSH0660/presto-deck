# HTMX with REST API
    <button class="button is-link mt-3" hx-post="https://jsonplaceholder.typicode.com/posts" hx-target="#rest-api-results" hx-vals="{&quot;title&quot;: &quot;foo&quot;, &quot;body&quot;: &quot;bar&quot;, &quot;userId&quot;: 1}">
            Fetch Posts
    </button>

# Basic AJAX Request
    <button class="button is-primary mt-4" hx-get="/demo/basic-ajax-response.html" hx-target=".box #basic-ajax-result" hx-swap="innerHTML">
        Make AJAX Request
    </button>

# Dynamic Form Validation
    <form id="dynamic-validation-form" hx-post="/demo/dynamic-form-validation" hx-trigger="keyup changed delay:300ms from:input" hx-target="#validation-messages" hx-swap="innerHTML" autocomplete="off">
        <input type="hidden" name="csrfmiddlewaretoken" value="8qxtYSvnQBx4VLwrfpEDWU3oLsDmg2Q9BvOP1ZUzNsmY5uWuiEwnI5gXcGP1Rmef">
        <div class="field">
            <label class="label" for="username">Username</label>
            <div class="control">
                <input class="input" type="text" id="username" name="username" placeholder="Enter username" required="">
            </div>
        </div>
        <div class="field">
            <label class="label" for="email">Email</label>
            <div class="control">
                <input class="input" type="email" id="email" name="email" placeholder="Enter email" required="" novalidate="">
            </div>
        </div>
        <div id="validation-messages" class="mt-3"></div>
        <button class="button is-primary mt-4" type="submit">
            Submit
        </button>
    </form>

# Autocomplete Search
    <div class="control has-icons-left">
        <input class="input is-medium" type="text" id="live-search-input" name="q" placeholder="Search users, products, etc..." autocomplete="off" hx-get="/demo/live-search-suggestions.html" hx-trigger="keyup changed delay:300ms" hx-target="#live-search-suggestions" hx-indicator="#live-search-indicator">
        <span class="icon is-left">
            <i class="fas fa-search"></i>
        </span>
        <span id="live-search-indicator" class="icon is-right" style="display:none;">
            <i class="fas fa-spinner fa-spin"></i>
        </span>
    </div>

# Interactive Like Button
    <form hx-post="/demo/like-button" hx-target="#like-button-container" hx-swap="outerHTML" hx-vals="{}" style="display: inline-block;">
        <button type="submit" class="button is-large is-rounded" style="font-size: 2rem; transition: color 0.2s;" aria-pressed="false">
            <span class="icon is-large">
                <i class="fas fa-heart-broken"></i>
            </span>
            <span style="font-size: 1.2rem; margin-left: 0.5em;">
                42
            </span>
        </button>
    </form>

# Active Search
    <div class="control has-icons-left">
        <input class="input is-medium" type="text" id="active-search-input" name="q" placeholder="Search for people, products, etc..." autocomplete="off" hx-get="/demo/active-search-results.html" hx-trigger="keyup changed delay:300ms" hx-target="#active-search-results" hx-indicator="#active-search-indicator">
        <span class="icon is-left">
            <i class="fas fa-search"></i>
        </span>
        <span id="active-search-indicator" class="icon is-right" style="display:none;">
            <i class="fas fa-spinner fa-spin"></i>
        </span>
    </div>

# Infinite Scroll
    <span id="infinite-scroll-loader" hx-get="/demo/infinite-scroll-items?page=2" hx-trigger="intersect once" hx-swap="afterend" class="has-text-centered py-4" style="min-height: 1px;" data-scroll-loader=""></span>

# Click to Edit
    <span id="infinite-scroll-loader" hx-get="/demo/infinite-scroll-items?page=2" hx-trigger="intersect once" hx-swap="afterend" class="has-text-centered py-4" style="min-height: 1px;" data-scroll-loader=""></span>

# Master/Detail View
    <a href="#" hx-get="/demo/master-detail-detail.html?id=1" hx-target="#detail-panel" hx-swap="innerHTML" class="is-active" data-detail-id="1">Alice Johnson</a>

# File Upload
    <form id="file-upload-form" hx-post="/demo/file-upload-result.html" hx-target="#file-upload-result" hx-encoding="multipart/form-data" enctype="multipart/form-data" _="on htmx:xhr:progress(loaded, total) set #progress.value to (loaded/total)*100">
                <div class="field">
                    <div class="file has-name is-boxed is-fullwidth">
                        <label class="file-label">
                            <input class="file-input" type="file" name="file" required="">
                            <span class="file-cta">
                                <span class="icon"><i class="fas fa-upload"></i></span>
                                <span class="file-label">Choose a file…</span>
                            </span>
                            <span class="file-name" id="file-upload-filename">No file selected</span>
                        </label>
                    </div>
                </div>
                <button class="button is-primary mt-3" type="submit">
                    <span class="icon"><i class="fas fa-cloud-upload-alt"></i></span>
                    <span>Upload</span>
                </button>
                <progress id="progress" value="0" max="100"></progress>
            </form>
        <div>
        <div id="file-upload-result" class="mt-4"></div>
    </div>

    <script>
        // Show selected file name in the UI
        // This must be re-attached after HTMX swaps the modal content!
        function attachFileInputListener() {
            var input = document.querySelector('#file-upload-form input[type="file"]');
            var nameSpan = document.getElementById('file-upload-filename');
            if (input && nameSpan) {
                input.addEventListener('change', function() {
                    nameSpan.textContent = input.files.length > 0 ? input.files[0].name : 'No file selected';
                });
            }
        }
        document.addEventListener('DOMContentLoaded', attachFileInputListener);
        document.body.addEventListener('htmx:afterSwap', function(evt) {
            // Only re-attach if the file upload form is present in the swapped content
            if (document.getElementById('file-upload-form')) {
                attachFileInputListener();
            }
        });
    </script>

# Polling Example
    <div id="polling-demo" hx-get="/demo/polling-fragment" hx-trigger="every 2s" hx-target="this" hx-swap="innerHTML" class="has-background-light p-4 mt-4" style="font-size:1.2em;">
        <!-- Initial content will be loaded here -->
        <span class="icon is-large"><i class="fas fa-sync fa-spin"></i></span>
        <span>Loading...</span>
    </div>

# Modal Dialog
    <button class="button is-primary" id="open-modal-btn" hx-get="/demo/modal-dialog-content" hx-target="#htmx-modal .modal-content" hx-trigger="click" hx-swap="innerHTML">
            Open Modal Dialog
        </button>

# Lazy Load Images
    <img src="https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400" alt="Lazy loaded image 1" style="width:100%; height:220px; object-fit:cover; border-radius:8px;" loading="lazy" class="">

# Progress Bar
    <button class="button is-primary" id="start-progress-btn" hx-get="/demo/progress-bar" hx-target="#progress-bar-result" hx-indicator="#progress-bar" hx-swap="innerHTML">
        Start Long-Running Request
    </button>
    <div id="progress-bar-result" class="mt-4"></div>

# Drag and Drop
    <form>
        <div class="field">
            <label class="label">Category</label>
            <div class="control">
                <div class="select">
                    <select id="category-select" name="category" hx-get="/demo/dependent-dropdown-options" hx-target="#item-select-container" hx-trigger="change" hx-indicator="#dropdown-indicator" required="">
                        <option value="">-- Choose a category --</option>
                        <option value="fruits">Fruits</option>
                        <option value="vegetables">Vegetables</option>
                        <option value="animals">Animals</option>
                    </select>
                </div>
            </div>
        </div>
        <div class="field">
            <label class="label">Item</label>
            <div class="control" id="item-select-container"><div class="select">
        <select id="item-select" name="item">
            <option value="">-- Choose an item --</option>
                <option value="apple">Apple</option>
                <option value="banana">Banana</option>
                <option value="orange">Orange</option>
                <option value="pear">Pear</option>
        </select>
        </div>
        </div>
            <span id="dropdown-indicator" class="icon is-small" style="display:none;">
                <i class="fas fa-spinner fa-spin"></i>
            </span>
        </div>
    </form>
# Toast Notification
    <form id="toast-form" hx-post="/demo/toast-notify" hx-target="#toast-container" hx-swap="beforeend" autocomplete="off">
        <div class="field has-addons">
            <div class="control is-expanded">
                <input class="input" type="text" name="message" placeholder="Enter a message..." value="This is a toast notification!">
            </div>
            <div class="control">
                <div class="select">
                    <select name="level">
                        <option value="info">Info</option>
                        <option value="success">Success</option>
                        <option value="warning">Warning</option>
                        <option value="danger">Danger</option>
                    </select>
                </div>
            </div>
            <div class="control">
                <button class="button is-primary" type="submit">
                    <span class="icon"><i class="fas fa-bell"></i></span>
                    <span>Show Toast</span>
                </button>
            </div>
        </div>
    </form>
