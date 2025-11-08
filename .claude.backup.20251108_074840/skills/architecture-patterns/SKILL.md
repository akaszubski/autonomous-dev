---
name: architecture-patterns
type: knowledge
description: This skill should be used when designing system architecture, making architectural decisions, or evaluating design patterns. It provides guidance on common patterns, ADR templates, design principles, and tradeoff analysis.
keywords: architecture, design, pattern, decision, tradeoffs, adr, system design, scalability, microservices, mvc, design patterns, solid
auto_activate: true
---

# Architecture Patterns Skill

Architectural design patterns, decision frameworks, and system design principles.

## When This Skill Activates

- Designing system architecture
- Writing Architecture Decision Records (ADRs)
- Evaluating design patterns
- Making architectural tradeoffs
- System design questions
- Keywords: "architecture", "design", "pattern", "adr", "system design", "scalability"

---

## Architecture Decision Records (ADRs)

### What is an ADR?

An ADR documents an architectural decision - the context, the decision made, and the consequences.

### When to Write an ADR

Write an ADR for decisions that:
- Are hard to reverse
- Impact multiple teams
- Involve significant tradeoffs
- Set precedents for future work

**Examples**:
- ✅ "We chose PostgreSQL over MongoDB"
- ✅ "We split the monolith into microservices"
- ✅ "We adopted event-driven architecture"
- ❌ "We renamed a function" (too trivial)
- ❌ "We fixed a bug" (not architectural)

### ADR Template

```markdown
# ADR-### [Short Title]

**Date**: YYYY-MM-DD
**Status**: [Proposed | Accepted | Deprecated | Superseded]
**Deciders**: [Names/Roles]

## Context

What is the issue we're trying to solve? What are the constraints?

Example:
> Our monolithic application has grown to 200K lines of code.
> Deploy times are 45+ minutes, and teams are blocked on each other.
> We need to improve deployment speed and team autonomy.

## Decision

What did we decide to do?

Example:
> We will split the monolith into domain-driven microservices,
> starting with the user service and order service.

## Alternatives Considered

What other options did we evaluate?

### Option 1: Keep the monolith
**Pros**: No migration cost, simpler deployment
**Cons**: Deploy times won't improve, team blocking continues

### Option 2: Modular monolith
**Pros**: Better than status quo, no network calls
**Cons**: Still single deployment unit, doesn't solve deploy time

### Option 3: Microservices (chosen)
**Pros**: Independent deploys, team autonomy, scalability
**Cons**: Complexity, network calls, distributed system challenges

## Consequences

### Positive
- Deploy times drop from 45min to 5min per service
- Teams can deploy independently
- Services can scale independently

### Negative
- Need service mesh (added complexity)
- Distributed tracing required
- Data consistency challenges

### Neutral
- Migration will take 6 months
- Need to train team on distributed systems

## Implementation Notes

- Phase 1: Extract user service (Month 1-2)
- Phase 2: Extract order service (Month 3-4)
- Phase 3: Extract payment service (Month 5-6)
- Use API gateway for routing
- Adopt Kubernetes for orchestration

## References

- [Martin Fowler - Microservices](https://martinfowler.com/articles/microservices.html)
- Internal: `docs/microservices-migration-plan.md`

---

**Supersedes**: [ADR-005] if this replaces an earlier decision
**Superseded by**: [ADR-015] if a later decision overrides this
```

### ADR Lifecycle

1. **Proposed**: Draft for review
2. **Accepted**: Team approved, implementing
3. **Deprecated**: No longer recommended, but not replaced
4. **Superseded**: Replaced by a newer ADR

---

## Common Architecture Patterns

### 1. Layered (N-Tier) Architecture

**Structure**:
```
┌─────────────────────────┐
│   Presentation Layer    │  (UI, Controllers)
├─────────────────────────┤
│    Business Logic       │  (Services, Domain)
├─────────────────────────┤
│    Data Access Layer    │  (Repositories, ORM)
├─────────────────────────┤
│       Database          │  (PostgreSQL, MySQL)
└─────────────────────────┘
```

**When to use**: Traditional web applications, CRUD-heavy systems

**Pros**:
- Simple to understand and implement
- Clear separation of concerns
- Easy to test each layer independently

**Cons**:
- Can become monolithic
- Changes ripple through layers
- Performance overhead from layer boundaries

**Example use case**: E-commerce website, internal business tools

---

### 2. Microservices Architecture

**Structure**:
```
┌────────────┐  ┌────────────┐  ┌────────────┐
│   User     │  │   Order    │  │  Payment   │
│  Service   │  │  Service   │  │  Service   │
└────────────┘  └────────────┘  └────────────┘
      │               │               │
      └───────────────┴───────────────┘
                  │
            ┌──────────────┐
            │ API Gateway  │
            └──────────────┘
```

**When to use**: Large teams, independent deployment needs, high scalability requirements

**Pros**:
- Independent deployment and scaling
- Team autonomy
- Technology diversity possible
- Fault isolation

**Cons**:
- Distributed system complexity
- Network latency
- Data consistency challenges
- Higher operational overhead

**Example use case**: Netflix, Amazon, large-scale SaaS platforms

---

### 3. Event-Driven Architecture

**Structure**:
```
┌────────────┐                   ┌────────────┐
│  Service A │───► Event Bus ───►│  Service B │
└────────────┘     (Kafka)       └────────────┘
                      │
                      ▼
                ┌────────────┐
                │  Service C │
                └────────────┘
```

**When to use**: Real-time systems, async workflows, event sourcing

**Pros**:
- Loose coupling between services
- Highly scalable
- Natural fit for real-time/streaming
- Easy to add new consumers

**Cons**:
- Debugging is harder (distributed traces)
- Event ordering challenges
- At-least-once/exactly-once semantics complexity

**Example use case**: Stock trading platforms, IoT systems, real-time analytics

---

### 4. Hexagonal Architecture (Ports & Adapters)

**Structure**:
```
         ┌──────────────────────┐
         │   Domain Logic       │
         │   (Business Rules)   │
         └──────────────────────┘
                  ▲    ▲
                  │    │
            ┌─────┘    └─────┐
            │                │
       ┌────▼────┐      ┌────▼────┐
       │  HTTP   │      │Database │
       │ Adapter │      │ Adapter │
       └─────────┘      └─────────┘
```

**When to use**: Domain-driven design, testability is critical

**Pros**:
- Business logic isolated from infrastructure
- Easy to test (mock adapters)
- Easy to swap implementations (e.g., swap database)

**Cons**:
- More initial setup
- Can be over-engineering for simple CRUD

**Example use case**: Banking systems, healthcare applications (domain-heavy)

---

### 5. Serverless Architecture

**Structure**:
```
API Gateway → Lambda → DynamoDB
            → Lambda → S3
            → Lambda → SQS
```

**When to use**: Variable/unpredictable load, event-driven tasks

**Pros**:
- No server management
- Pay-per-use pricing
- Auto-scaling
- Fast to deploy

**Cons**:
- Cold start latency
- Vendor lock-in
- Debugging is harder
- Limited execution time

**Example use case**: Image processing, webhooks, scheduled jobs

---

## Design Patterns (Gang of Four)

### Creational Patterns

#### Singleton

**Purpose**: Ensure only one instance exists

```python
class DatabaseConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.connection = create_connection()
        return cls._instance

# Usage
db1 = DatabaseConnection()  # Creates instance
db2 = DatabaseConnection()  # Returns same instance
assert db1 is db2  # True
```

**When to use**: Shared resources (DB connection, config, cache)

**Caution**: Can make testing difficult (global state)

---

#### Factory Pattern

**Purpose**: Create objects without specifying exact class

```python
class PaymentProcessorFactory:
    @staticmethod
    def create(payment_type: str):
        if payment_type == "credit_card":
            return CreditCardProcessor()
        elif payment_type == "paypal":
            return PayPalProcessor()
        elif payment_type == "crypto":
            return CryptoProcessor()
        raise ValueError(f"Unknown payment type: {payment_type}")

# Usage
processor = PaymentProcessorFactory.create("credit_card")
processor.process(amount=100)
```

**When to use**: Object creation logic is complex or conditional

---

### Structural Patterns

#### Adapter Pattern

**Purpose**: Make incompatible interfaces work together

```python
# Legacy system
class OldLogger:
    def log_message(self, msg):
        print(f"[OLD] {msg}")

# New interface
class Logger:
    def log(self, level, message):
        pass

# Adapter
class OldLoggerAdapter(Logger):
    def __init__(self, old_logger):
        self.old_logger = old_logger

    def log(self, level, message):
        self.old_logger.log_message(f"{level}: {message}")

# Usage
old = OldLogger()
adapter = OldLoggerAdapter(old)
adapter.log("INFO", "System started")  # Works with new interface!
```

**When to use**: Integrating legacy code, third-party libraries

---

#### Decorator Pattern

**Purpose**: Add behavior to objects dynamically

```python
# Base
class Coffee:
    def cost(self):
        return 2.00

# Decorators
class MilkDecorator:
    def __init__(self, coffee):
        self.coffee = coffee

    def cost(self):
        return self.coffee.cost() + 0.50

class SugarDecorator:
    def __init__(self, coffee):
        self.coffee = coffee

    def cost(self):
        return self.coffee.cost() + 0.25

# Usage
coffee = Coffee()
coffee = MilkDecorator(coffee)
coffee = SugarDecorator(coffee)
print(coffee.cost())  # 2.75
```

**When to use**: Add responsibilities without subclassing

---

### Behavioral Patterns

#### Strategy Pattern

**Purpose**: Select algorithm at runtime

```python
from abc import ABC, abstractmethod

class TrainingStrategy(ABC):
    @abstractmethod
    def train(self, model, data):
        pass

class LoRAStrategy(TrainingStrategy):
    def train(self, model, data):
        # LoRA-specific training
        pass

class DPOStrategy(TrainingStrategy):
    def train(self, model, data):
        # DPO-specific training
        pass

class Trainer:
    def __init__(self, strategy: TrainingStrategy):
        self.strategy = strategy

    def run(self, model, data):
        self.strategy.train(model, data)

# Usage
trainer = Trainer(LoRAStrategy())
trainer.run(model, data)

# Switch strategy
trainer.strategy = DPOStrategy()
trainer.run(model, data)
```

**When to use**: Multiple algorithms, select at runtime

---

#### Observer Pattern

**Purpose**: Notify dependents when state changes

```python
class Subject:
    def __init__(self):
        self._observers = []

    def attach(self, observer):
        self._observers.append(observer)

    def notify(self, event):
        for observer in self._observers:
            observer.update(event)

class Logger:
    def update(self, event):
        print(f"[LOG] {event}")

class EmailNotifier:
    def update(self, event):
        print(f"[EMAIL] Sending alert for: {event}")

# Usage
order_system = Subject()
order_system.attach(Logger())
order_system.attach(EmailNotifier())

order_system.notify("Order placed")  # Both observers notified
```

**When to use**: Event systems, publish-subscribe patterns

---

## System Design Principles

### SOLID Principles

#### S - Single Responsibility

**Rule**: A class should have ONE reason to change

```python
# ❌ BAD: Multiple responsibilities
class User:
    def save_to_database(self): ...
    def send_email(self): ...
    def generate_report(self): ...

# ✅ GOOD: Single responsibility
class User:
    pass

class UserRepository:
    def save(self, user): ...

class EmailService:
    def send_welcome_email(self, user): ...

class ReportGenerator:
    def generate_user_report(self, user): ...
```

---

#### O - Open/Closed

**Rule**: Open for extension, closed for modification

```python
# ❌ BAD: Must modify class to add new shapes
class AreaCalculator:
    def calculate(self, shapes):
        total = 0
        for shape in shapes:
            if shape.type == "circle":
                total += 3.14 * shape.radius ** 2
            elif shape.type == "square":
                total += shape.side ** 2
        return total

# ✅ GOOD: Extend via new classes
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self):
        pass

class Circle(Shape):
    def area(self):
        return 3.14 * self.radius ** 2

class Square(Shape):
    def area(self):
        return self.side ** 2

class AreaCalculator:
    def calculate(self, shapes):
        return sum(shape.area() for shape in shapes)
```

---

#### L - Liskov Substitution

**Rule**: Subtypes must be substitutable for base types

```python
# ❌ BAD: Violates LSP
class Bird:
    def fly(self): pass

class Penguin(Bird):  # Penguins can't fly!
    def fly(self):
        raise NotImplementedError("Penguins can't fly")

# ✅ GOOD: Proper hierarchy
class Bird:
    pass

class FlyingBird(Bird):
    def fly(self): pass

class Sparrow(FlyingBird):
    def fly(self): ...

class Penguin(Bird):
    def swim(self): ...
```

---

#### I - Interface Segregation

**Rule**: Many specific interfaces > one general interface

```python
# ❌ BAD: Fat interface
class Worker:
    def work(self): pass
    def eat(self): pass

class Robot(Worker):  # Robots don't eat!
    def eat(self):
        raise NotImplementedError()

# ✅ GOOD: Segregated interfaces
class Workable:
    def work(self): pass

class Eatable:
    def eat(self): pass

class Human(Workable, Eatable):
    def work(self): ...
    def eat(self): ...

class Robot(Workable):
    def work(self): ...
```

---

#### D - Dependency Inversion

**Rule**: Depend on abstractions, not concretions

```python
# ❌ BAD: Depends on concrete class
class EmailService:
    pass

class NotificationManager:
    def __init__(self):
        self.email = EmailService()  # Hard dependency!

# ✅ GOOD: Depends on abstraction
from abc import ABC, abstractmethod

class Notifier(ABC):
    @abstractmethod
    def send(self, message): pass

class EmailNotifier(Notifier):
    def send(self, message): ...

class SMSNotifier(Notifier):
    def send(self, message): ...

class NotificationManager:
    def __init__(self, notifier: Notifier):
        self.notifier = notifier  # Depends on abstraction
```

---

### Other Key Principles

#### DRY (Don't Repeat Yourself)

**Rule**: Every piece of knowledge should have a single representation

```python
# ❌ BAD: Duplicated validation
def create_user(email):
    if "@" not in email:
        raise ValueError("Invalid email")
    ...

def update_user(email):
    if "@" not in email:  # Duplicated!
        raise ValueError("Invalid email")
    ...

# ✅ GOOD: Single source of truth
def validate_email(email):
    if "@" not in email:
        raise ValueError("Invalid email")

def create_user(email):
    validate_email(email)
    ...

def update_user(email):
    validate_email(email)
    ...
```

---

#### KISS (Keep It Simple, Stupid)

**Rule**: Simplest solution that works

```python
# ❌ BAD: Over-engineered
class AbstractFactoryBuilderSingletonProxy:
    def create_instance_with_dependency_injection():
        ...

# ✅ GOOD: Simple and clear
def create_user(name, email):
    return User(name=name, email=email)
```

---

#### YAGNI (You Aren't Gonna Need It)

**Rule**: Don't add functionality until needed

```python
# ❌ BAD: Adding features "just in case"
class User:
    def export_to_json(self): ...
    def export_to_xml(self): ...  # Do we need XML?
    def export_to_yaml(self): ...  # Do we need YAML?
    def export_to_csv(self): ...   # Do we need CSV?

# ✅ GOOD: Only what's needed now
class User:
    def export_to_json(self):  # Only JSON needed right now
        ...
```

---

## Tradeoff Analysis Framework

### Performance vs. Simplicity

| Approach | Performance | Simplicity | When to Use |
|----------|-------------|------------|-------------|
| In-memory cache | ⭐⭐⭐ | ⭐⭐ | Hot data, read-heavy |
| Database query | ⭐ | ⭐⭐⭐ | Simple CRUD, occasional access |
| Redis cache | ⭐⭐ | ⭐ | Distributed caching needed |

---

### Consistency vs. Availability (CAP Theorem)

**Rule**: In a distributed system, you can have at most 2 of 3:
- **C**onsistency: All nodes see same data
- **A**vailability: Every request gets a response
- **P**artition tolerance: System works despite network splits

**Choices**:
- **CP**: Consistency + Partition Tolerance (e.g., MongoDB, HBase)
- **AP**: Availability + Partition Tolerance (e.g., Cassandra, DynamoDB)
- **CA**: Not possible in distributed systems (network partitions happen!)

---

### Coupling vs. Cohesion

**Goal**: Low coupling, high cohesion

```python
# ❌ BAD: High coupling, low cohesion
class OrderProcessor:
    def __init__(self, db, email, payment, inventory):
        self.db = db
        self.email = email
        self.payment = payment
        self.inventory = inventory  # Coupled to 4 systems!

# ✅ GOOD: Low coupling, high cohesion
class OrderProcessor:
    def __init__(self, order_repository):
        self.repository = order_repository

class PaymentService:
    def process(self, order): ...

class InventoryService:
    def reserve(self, items): ...
```

---

## Integration with [PROJECT_NAME]

[PROJECT_NAME] architectural principles:

- **Patterns**: Hexagonal architecture, event-driven for async tasks
- **ADRs**: Document all major decisions in `docs/adr/`
- **Principles**: SOLID, DRY, KISS, YAGNI
- **Design reviews**: All major architecture changes reviewed before implementation
- **Tradeoff documentation**: Explain WHY we chose an approach

---

## Additional Resources

**Books**:
- "Design Patterns" by Gang of Four
- "Clean Architecture" by Robert Martin
- "Software Architecture: The Hard Parts" by Neal Ford
- "Building Microservices" by Sam Newman

**Websites**:
- [Martin Fowler's Architecture Patterns](https://martinfowler.com/architecture/)
- [Microsoft Azure Architecture Center](https://docs.microsoft.com/en-us/azure/architecture/)
- [AWS Architecture Center](https://aws.amazon.com/architecture/)

---

**Version**: 1.0.0
**Type**: Knowledge skill (no scripts)
**See Also**: documentation-guide (for ADR formatting), python-standards, code-review
