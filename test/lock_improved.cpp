#include <iostream>
#include <thread>
#include <vector>
#include <chrono>
#include <numeric>

// --- The High-Performance Solution ---

// 'thread_local' is the key to this improvement. It creates a separate
// instance of this variable for each thread. There is no shared data.
thread_local long long t_local_counter = 0;
//Each thread will execute this code on its own private data, so no locks are needed.
void improved_worker_function(long iterations) {
    for (long i = 0; i < iterations; ++i) {
        t_local_counter++;
    }
}

// --- Main Application Logic ---

int main(int argc, char* argv[]) {
    int num_threads = 8;
    long iterations_per_thread = 500000;

    if (argc == 3) {
        num_threads = std::stoi(argv[1]);
        iterations_per_thread = std::stol(argv[2]);
    }

    std::cout << "Starting IMPROVED lock-free demo..." << std::endl;
    std::cout << " - Threads: " << num_threads << std::endl;
    std::cout << " - Iterations per thread: " << iterations_per_thread << std::endl;
    long long expected_total = (long long)num_threads * iterations_per_thread;
    std::cout << " - Total increments: " << expected_total << std::endl;

    // --- Thread Creation & Execution ---
    std::vector<std::thread> threads;
    threads.reserve(num_threads);

    // This vector will collect the final result from each thread's private counter.
    std::vector<long long> local_results(num_threads);

    auto start_time = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < num_threads; ++i) {
        // We use a lambda to run the worker and then capture its final result.
        threads.emplace_back([&, i]() {
            improved_worker_function(iterations_per_thread);
            // After this thread is done, store its final private count
            // into the results vector in the main thread.
            local_results[i] = t_local_counter;
        });
    }

    // --- Wait for all threads to finish ---
    for (auto& t : threads) {
        t.join();
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;

    // --- Verification and Final Results ---

    // Sum the results from all the private thread counters to get the grand total.
    long long final_counter = std::accumulate(local_results.begin(), local_results.end(), 0LL);
    
    std::cout << "\nAll threads finished." << std::endl;
    std::cout << "Final counter value: " << final_counter 
              << (final_counter == expected_total ? " (Correct!)" : " (Incorrect!)") << std::endl;
    std::cout << "Total execution time: " << elapsed.count() << " seconds" << std::endl;

    return 0;
}
