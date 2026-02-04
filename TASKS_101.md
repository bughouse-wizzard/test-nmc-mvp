# Task 101: Setup Celery Worker & Queue

## Overview
Configure Celery in `app/core/celery_app.py`. Create a task `run_search_task(search_id)` in `app/worker.py`. This task should fetch the SearchRequest from DB, update status to RUNNING, call the scraper, and save initial `ContractResult` rows (with basic info). Implement the 'Stop' logic check within the loop.

## Plan

### Phase 1: Exploration and Analysis
- [x] Explore project structure and understand existing codebase
- [x] Check existing Celery configuration in `app/workers/celery_app.py`
- [x] Check existing tasks in `app/workers/tasks.py`
- [x] Examine database models (SearchRequest, ContractResult)
- [x] Understand current task implementation

### Phase 2: Create Celery Configuration in `app/core/celery_app.py`
- [x] Create `app/core/celery_app.py` with proper Celery configuration
- [x] Configure broker and backend from settings
- [x] Set up task routes and queues
- [x] Configure task time limits and retry policies

### Phase 3: Create `app/worker.py` with `run_search_task`
- [x] Create `app/worker.py` file
- [x] Implement `run_search_task(search_id)` function
- [x] Add logic to fetch SearchRequest from database
- [x] Update SearchRequest status to RUNNING
- [x] Implement scraper call (placeholder or integration)
- [x] Save initial ContractResult rows with basic info
- [x] Implement 'Stop' logic check within the loop

### Phase 4: Integrate with Existing System
- [x] Check if scraper module exists or needs to be created
- [x] Ensure proper database session handling
- [x] Test task execution flow
- [x] Verify error handling and retry logic

### Phase 5: Testing and Validation
- [x] Test Celery worker startup
- [x] Test task execution with sample data
- [x] Verify database updates
- [x] Test 'Stop' logic functionality

### Phase 6: Finalization
- [x] Commit changes
- [ ] Push to remote branch `ai-feat-task_101_2ad66409113a45aba21c0d70d7afe679`